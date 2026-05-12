"""
Argus AI Trainer — Pack 45.

Sistema ML híbrido pure-Python (cero deps externas) para clasificar jugadores
como cheaters/limpios con explicabilidad y aprendizaje continuo.

Componentes:
  1. **LogisticRegression** — clasificador principal con SGD + L2 regularization
     + Platt scaling para calibración de probabilidades.
  2. **KNNCheaterClassifier** — clasificación por proximidad a perfiles ya
     etiquetados (cheaters confirmados vs limpios confirmados).
  3. **TemporalPatternDetector** — Markov chain de transiciones entre violations
     consecutivas. Detecta secuencias típicas de cheaters (ej:
     killaura_no_swing -> reach -> killaura_multi en pocos segundos).
  4. **Ensemble** — combina las 3 señales + el score heurístico legacy con
     pesos adaptativos según samples disponibles.

Diseño:
  - Estado del modelo se serializa a JSON (lista de floats) → DB.
  - Toda predicción retorna `EnsembleResult` con score, contribución por
    componente, top features. Explicabilidad first-class.
  - Online updates: cada feedback nuevo se aplica con SGD step para
    aprendizaje incremental sin reentrenar todo.
  - Batch retraining periódico para evitar drift.
  - Determinismo: random.seed configurable para reproducibilidad.
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Any


# ──────────────────────────────────────────────────────────────────────
#  Utilities
# ──────────────────────────────────────────────────────────────────────

def sigmoid(z: float) -> float:
    """Sigmoide estable numéricamente (evita overflow para |z| grande)."""
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    else:
        ez = math.exp(z)
        return ez / (1.0 + ez)


def safe_log(x: float, eps: float = 1e-12) -> float:
    return math.log(max(eps, x))


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def euclidean_distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot(a, b) / (na * nb)


# ──────────────────────────────────────────────────────────────────────
#  Logistic Regression con SGD + L2 + Platt scaling
# ──────────────────────────────────────────────────────────────────────

@dataclass
class LogRegState:
    """Estado serializable del clasificador. Es lo que se guarda en DB."""
    weights: list[float]
    bias: float
    feature_names: list[str]
    # Normalización: media y stddev por feature (training-time stats).
    # Lo aplicamos a inputs antes de scoring para estabilidad numérica.
    feature_mean: list[float]
    feature_std: list[float]
    # Platt scaling params (sigmoid post-cal): out = sigmoid(a * raw + b)
    platt_a: float = 1.0
    platt_b: float = 0.0
    # Training metadata
    samples_trained: int = 0
    last_loss: float = 0.0
    last_accuracy: float = 0.0
    last_precision: float = 0.0
    last_recall: float = 0.0
    last_f1: float = 0.0
    last_trained_at: float = 0.0
    version: int = 1


class LogisticRegression:
    """
    Logistic Regression online con SGD y L2 regularization.

    - `partial_fit(x, y, sample_weight=1.0)` para updates incrementales (un sample).
    - `fit(X, y, sample_weights=None, epochs=N)` para batch training.
    - `predict_proba(x)` devuelve P(cheater | x) ∈ [0,1], calibrado con Platt.
    - `feature_importance()` devuelve lista de (feature, |weight|) descendente.

    Convención de labels:
        y = 1 → cheater confirmado
        y = 0 → limpio confirmado

    Para soft labels (0.6, 0.3, etc.), pasarlos como float y se interpolan vía
    cross-entropy continua. Útil para auto-labels con confianza intermedia.
    """

    def __init__(self,
                 feature_names: list[str],
                 lr: float = 0.05,
                 l2: float = 1e-4,
                 seed: int = 42):
        self.feature_names = list(feature_names)
        self.n = len(feature_names)
        self.lr = lr
        self.l2 = l2
        rng = random.Random(seed)
        # Inicialización Xavier (uniforme escalado por sqrt(2/n))
        scale = math.sqrt(2.0 / max(1, self.n))
        self.weights = [rng.uniform(-scale, scale) for _ in range(self.n)]
        self.bias = 0.0
        self.feature_mean = [0.0] * self.n
        self.feature_std = [1.0] * self.n
        self.platt_a = 1.0
        self.platt_b = 0.0
        self.samples_trained = 0
        self.last_loss = 0.0
        self.last_accuracy = 0.0
        self.last_precision = 0.0
        self.last_recall = 0.0
        self.last_f1 = 0.0
        self.last_trained_at = 0.0
        self.version = 1

    # ── Normalization ─────────────────────────────────────────────

    def _normalize(self, x: list[float]) -> list[float]:
        out = [0.0] * self.n
        for i in range(self.n):
            std = self.feature_std[i] if self.feature_std[i] > 1e-9 else 1.0
            out[i] = (x[i] - self.feature_mean[i]) / std
        return out

    def _compute_normalization(self, X: list[list[float]]) -> None:
        """Calcula media y stddev por columna sobre el training set."""
        n_samples = len(X)
        if n_samples == 0:
            return
        for i in range(self.n):
            col = [row[i] for row in X]
            mean = sum(col) / n_samples
            var = sum((v - mean) ** 2 for v in col) / max(1, n_samples - 1)
            std = math.sqrt(var) if var > 1e-12 else 1.0
            self.feature_mean[i] = mean
            self.feature_std[i] = std

    # ── Prediction ────────────────────────────────────────────────

    def _raw_score(self, x_norm: list[float]) -> float:
        return dot(self.weights, x_norm) + self.bias

    def predict_proba(self, x: list[float]) -> float:
        if len(x) != self.n:
            return 0.5  # malformed → uncertain
        x_norm = self._normalize(x)
        raw = self._raw_score(x_norm)
        # Platt scaling para calibrar
        calibrated = self.platt_a * raw + self.platt_b
        return sigmoid(calibrated)

    def predict_proba_uncalibrated(self, x: list[float]) -> float:
        """Versión sin Platt scaling — útil para debug."""
        x_norm = self._normalize(x)
        return sigmoid(self._raw_score(x_norm))

    # ── SGD step ──────────────────────────────────────────────────

    def partial_fit(self,
                    x: list[float],
                    y: float,
                    sample_weight: float = 1.0) -> float:
        """
        Un step de SGD con un solo sample. Devuelve la loss antes del update.

        y es float ∈ [0, 1]; permite soft labels.
        """
        if len(x) != self.n:
            return 0.0
        x_norm = self._normalize(x)
        p = sigmoid(self._raw_score(x_norm))
        # Binary cross-entropy
        loss = -(y * safe_log(p) + (1.0 - y) * safe_log(1.0 - p))
        loss += 0.5 * self.l2 * sum(w * w for w in self.weights)
        # Gradient: dL/dw_i = (p - y) * x_i + l2 * w_i
        grad_bias = (p - y) * sample_weight
        for i in range(self.n):
            grad = (p - y) * x_norm[i] * sample_weight + self.l2 * self.weights[i]
            self.weights[i] -= self.lr * grad
        self.bias -= self.lr * grad_bias
        self.samples_trained += 1
        return loss

    def fit(self,
            X: list[list[float]],
            y: list[float],
            sample_weights: list[float] | None = None,
            epochs: int = 30,
            recompute_normalization: bool = True,
            shuffle: bool = True,
            verbose: bool = False) -> dict[str, float]:
        """
        Batch training. Recalcula normalization, hace shuffle por epoch,
        y ajusta Platt scaling al final con un held-out 20% split.
        """
        n_samples = len(X)
        if n_samples == 0:
            return {"loss": 0.0, "accuracy": 0.0}
        if sample_weights is None:
            sample_weights = [1.0] * n_samples

        if recompute_normalization:
            self._compute_normalization(X)

        # Stratified split 80/20: respetar proporción de clases
        rng = random.Random(7)
        idxs_pos = [i for i, v in enumerate(y) if v >= 0.5]
        idxs_neg = [i for i, v in enumerate(y) if v < 0.5]
        rng.shuffle(idxs_pos)
        rng.shuffle(idxs_neg)
        cut_p = int(0.8 * len(idxs_pos))
        cut_n = int(0.8 * len(idxs_neg))
        train_idx = idxs_pos[:cut_p] + idxs_neg[:cut_n]
        val_idx   = idxs_pos[cut_p:] + idxs_neg[cut_n:]
        if not val_idx:  # muy pocos samples; usar todo para training
            val_idx = train_idx

        last_loss = 0.0
        for epoch in range(epochs):
            indices = list(train_idx)
            if shuffle:
                rng.shuffle(indices)
            epoch_loss = 0.0
            for idx in indices:
                epoch_loss += self.partial_fit(X[idx], y[idx], sample_weights[idx])
            avg_loss = epoch_loss / max(1, len(indices))
            last_loss = avg_loss
            if verbose and (epoch == 0 or epoch == epochs - 1 or (epoch + 1) % 10 == 0):
                print(f"  [epoch {epoch+1}/{epochs}] loss={avg_loss:.4f}")

        # Platt scaling sobre validation set
        if len(val_idx) >= 4:
            val_raw = []
            val_y = []
            for idx in val_idx:
                x_norm = self._normalize(X[idx])
                val_raw.append(self._raw_score(x_norm))
                val_y.append(y[idx])
            self._fit_platt(val_raw, val_y)

        # Métricas en val set
        metrics = self._evaluate_indices(X, y, val_idx)
        self.last_loss = last_loss
        self.last_accuracy = metrics["accuracy"]
        self.last_precision = metrics["precision"]
        self.last_recall    = metrics["recall"]
        self.last_f1        = metrics["f1"]
        self.last_trained_at = time.time()
        self.version += 1
        metrics["loss"] = last_loss
        return metrics

    def _fit_platt(self, raw_scores: list[float], y: list[float]) -> None:
        """
        Platt scaling: ajusta y' = sigmoid(a*raw + b) con un MLE de regresión
        logística simple sobre (raw_score, y). Implementación pure-python con
        SGD (porque ya tenemos la maquinaria).
        """
        n = len(raw_scores)
        if n < 4:
            return
        # Inicialización
        a, b = 1.0, 0.0
        lr = 0.02
        for _ in range(200):
            for i in range(n):
                z = a * raw_scores[i] + b
                p = sigmoid(z)
                err = p - y[i]
                a -= lr * err * raw_scores[i]
                b -= lr * err
        self.platt_a = a
        self.platt_b = b

    def _evaluate_indices(self, X, y, idx) -> dict[str, float]:
        tp = fp = tn = fn = 0
        for i in idx:
            p = self.predict_proba(X[i])
            pred = 1 if p >= 0.5 else 0
            true = 1 if y[i] >= 0.5 else 0
            if pred == 1 and true == 1: tp += 1
            elif pred == 1 and true == 0: fp += 1
            elif pred == 0 and true == 0: tn += 1
            elif pred == 0 and true == 1: fn += 1
        n = tp + fp + tn + fn
        accuracy  = (tp + tn) / max(1, n)
        precision = tp / max(1, tp + fp)
        recall    = tp / max(1, tp + fn)
        f1 = 2 * precision * recall / max(1e-9, precision + recall)
        return {
            "accuracy":  round(accuracy, 4),
            "precision": round(precision, 4),
            "recall":    round(recall, 4),
            "f1":        round(f1, 4),
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        }

    # ── Feature importance ────────────────────────────────────────

    def feature_importance(self, top_k: int = 20) -> list[tuple[str, float]]:
        """Pesos absolutos descendentes — qué features pesan más."""
        items = [(self.feature_names[i], abs(self.weights[i]))
                 for i in range(self.n)]
        items.sort(key=lambda t: t[1], reverse=True)
        return items[:top_k]

    def signed_importance(self, x: list[float], top_k: int = 5) -> list[tuple[str, float]]:
        """
        Importancia firmada para una predicción concreta: weight_i * x_norm_i.
        Positivo → empuja hacia 'cheater'. Negativo → empuja hacia 'limpio'.
        """
        x_norm = self._normalize(x)
        contribs = [(self.feature_names[i], self.weights[i] * x_norm[i])
                    for i in range(self.n)]
        contribs.sort(key=lambda t: abs(t[1]), reverse=True)
        return contribs[:top_k]

    # ── Serialización ─────────────────────────────────────────────

    def to_state(self) -> LogRegState:
        return LogRegState(
            weights=list(self.weights),
            bias=self.bias,
            feature_names=list(self.feature_names),
            feature_mean=list(self.feature_mean),
            feature_std=list(self.feature_std),
            platt_a=self.platt_a,
            platt_b=self.platt_b,
            samples_trained=self.samples_trained,
            last_loss=self.last_loss,
            last_accuracy=self.last_accuracy,
            last_precision=self.last_precision,
            last_recall=self.last_recall,
            last_f1=self.last_f1,
            last_trained_at=self.last_trained_at,
            version=self.version,
        )

    @classmethod
    def from_state(cls, state: LogRegState | dict) -> "LogisticRegression":
        if isinstance(state, dict):
            state = LogRegState(**{k: v for k, v in state.items()
                                   if k in LogRegState.__dataclass_fields__})
        m = cls(feature_names=state.feature_names)
        m.weights = list(state.weights)
        m.bias = state.bias
        m.feature_mean = list(state.feature_mean)
        m.feature_std  = list(state.feature_std)
        m.platt_a = state.platt_a
        m.platt_b = state.platt_b
        m.samples_trained = state.samples_trained
        m.last_loss = state.last_loss
        m.last_accuracy = state.last_accuracy
        m.last_precision = state.last_precision
        m.last_recall = state.last_recall
        m.last_f1 = state.last_f1
        m.last_trained_at = state.last_trained_at
        m.version = state.version
        return m

    def to_json(self) -> str:
        return json.dumps(asdict(self.to_state()))

    @classmethod
    def from_json(cls, s: str) -> "LogisticRegression":
        return cls.from_state(json.loads(s))


# ──────────────────────────────────────────────────────────────────────
#  K-Nearest Neighbors (proximidad a perfiles conocidos)
# ──────────────────────────────────────────────────────────────────────

@dataclass
class KNNExample:
    """Un perfil conocido del feature space, con su etiqueta."""
    player_uuid: str
    player_name: str
    feature_vector: list[float]
    label: float  # 1.0 = cheater, 0.0 = clean
    weight: float = 1.0  # fuerza del label (auto-labels < explicit feedback)
    source: str = "unknown"
    timestamp: float = 0.0


class KNNCheaterClassifier:
    """
    K-NN clásico con normalización + distancia coseno (más robusta que
    euclideana frente a features con escalas distintas).

    Para clasificar un jugador X:
      1. Computar similitud coseno con todos los `KNNExample`s.
      2. Tomar los top-K más cercanos.
      3. Voto ponderado por similitud * weight.
      4. Retornar probabilidad + neighbors usados (explicabilidad).
    """

    def __init__(self,
                 feature_names: list[str],
                 k: int = 7,
                 min_examples: int = 3):
        self.feature_names = list(feature_names)
        self.n = len(feature_names)
        self.k = k
        self.min_examples = min_examples
        self.examples: list[KNNExample] = []

    def add_example(self, ex: KNNExample) -> None:
        if len(ex.feature_vector) != self.n:
            return
        # Reemplazar si ya tenemos este UUID (mantener data fresca)
        for i, e in enumerate(self.examples):
            if e.player_uuid == ex.player_uuid:
                self.examples[i] = ex
                return
        self.examples.append(ex)

    def remove_example(self, player_uuid: str) -> bool:
        before = len(self.examples)
        self.examples = [e for e in self.examples if e.player_uuid != player_uuid]
        return len(self.examples) < before

    def predict(self, x: list[float]) -> dict[str, Any]:
        if len(x) != self.n or len(self.examples) < self.min_examples:
            return {"score": 0.5, "confidence": 0.0, "neighbors": []}
        scored = []
        for ex in self.examples:
            sim = cosine_similarity(x, ex.feature_vector)
            scored.append((sim, ex))
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:self.k]
        # Voto ponderado
        weight_sum = 0.0
        positive = 0.0
        for sim, ex in top:
            # Convertir similitud [-1, 1] a peso [0, 1] (cheaters más cercanos pesan más)
            w = max(0.0, (sim + 1.0) / 2.0) * ex.weight
            weight_sum += w
            positive += w * ex.label
        if weight_sum < 1e-9:
            return {"score": 0.5, "confidence": 0.0, "neighbors": []}
        score = positive / weight_sum
        # Confianza: avg sim del top-K * (samples disponibles / 30 cap)
        avg_sim = sum(s for s, _ in top) / max(1, len(top))
        confidence = clamp(
            ((avg_sim + 1.0) / 2.0) * min(1.0, len(self.examples) / 30.0),
            0.0, 1.0
        )
        neighbors = [
            {
                "player_name": ex.player_name,
                "uuid": ex.player_uuid,
                "similarity": round((sim + 1.0) / 2.0, 4),
                "label": ex.label,
                "source": ex.source,
            }
            for sim, ex in top[:5]
        ]
        return {"score": round(score, 4),
                "confidence": round(confidence, 4),
                "neighbors": neighbors}

    def size(self) -> int:
        return len(self.examples)

    def class_counts(self) -> dict[str, int]:
        pos = sum(1 for e in self.examples if e.label >= 0.5)
        neg = sum(1 for e in self.examples if e.label < 0.5)
        return {"cheaters": pos, "clean": neg}

    # ── Persistencia ──────────────────────────────────────────────

    def to_json(self) -> str:
        return json.dumps({
            "feature_names": self.feature_names,
            "k": self.k,
            "min_examples": self.min_examples,
            "examples": [asdict(e) for e in self.examples],
        })

    @classmethod
    def from_json(cls, s: str) -> "KNNCheaterClassifier":
        d = json.loads(s)
        m = cls(feature_names=d["feature_names"],
                k=d.get("k", 7),
                min_examples=d.get("min_examples", 3))
        for ed in d.get("examples", []):
            m.examples.append(KNNExample(**ed))
        return m


# ──────────────────────────────────────────────────────────────────────
#  Temporal Pattern Detector (Markov order-2 sobre violations)
# ──────────────────────────────────────────────────────────────────────

class TemporalPatternDetector:
    """
    Analiza secuencias de violations consecutivas por jugador. Aprende qué
    transiciones (A → B) son frecuentes en cheaters vs limpios y produce un
    score basado en log-likelihood ratio.

    Ejemplo: la secuencia
        killaura_no_swing → killaura_yaw_snap → reach
    es muy típica de cheaters silent killaura. Mientras que
        chat_spam → chat_spam → chat_spam
    es spam de chat normal, no cheater killaura.

    Pure-python, sin numpy. El estado es 2 matrices de conteo (cheater /
    clean) que se actualizan con cada secuencia etiquetada.
    """

    def __init__(self):
        # transitions[A][B] = count de A→B observado en cheaters
        self.cheater_trans: dict[str, dict[str, float]] = {}
        self.clean_trans: dict[str, dict[str, float]] = {}
        # Marginal counts para suavizar
        self.cheater_counts: dict[str, float] = {}
        self.clean_counts: dict[str, float] = {}
        # Laplace smoothing
        self.alpha = 1.0
        self.samples_observed = 0

    def observe(self, sequence: list[str], label: float) -> None:
        """Registra una secuencia de check_names con su label (0/1)."""
        if not sequence or len(sequence) < 2:
            return
        target_trans  = self.cheater_trans if label >= 0.5 else self.clean_trans
        target_counts = self.cheater_counts if label >= 0.5 else self.clean_counts
        for i in range(len(sequence) - 1):
            a, b = sequence[i], sequence[i + 1]
            target_trans.setdefault(a, {})
            target_trans[a][b] = target_trans[a].get(b, 0.0) + 1.0
            target_counts[a] = target_counts.get(a, 0.0) + 1.0
        self.samples_observed += 1

    def score_sequence(self, sequence: list[str]) -> dict[str, float]:
        """
        Log-likelihood ratio entre P(seq | cheater) y P(seq | clean).
        Retorna un score [0, 1] vía sigmoid del LLR.
        """
        if not sequence or len(sequence) < 2:
            return {"score": 0.5, "llr": 0.0, "transitions": 0}
        llr = 0.0
        n_trans = 0
        vocab = set(self.cheater_counts.keys()) | set(self.clean_counts.keys())
        V = max(1, len(vocab))
        for i in range(len(sequence) - 1):
            a, b = sequence[i], sequence[i + 1]
            p_cheater = self._smoothed_prob(a, b, self.cheater_trans, self.cheater_counts, V)
            p_clean   = self._smoothed_prob(a, b, self.clean_trans, self.clean_counts, V)
            llr += safe_log(p_cheater) - safe_log(p_clean)
            n_trans += 1
        # Sigmoid del LLR escalado: a más transiciones, más confianza
        scaled_llr = llr / max(1, n_trans)
        score = sigmoid(scaled_llr)
        return {
            "score": round(score, 4),
            "llr": round(llr, 4),
            "scaled_llr": round(scaled_llr, 4),
            "transitions": n_trans,
        }

    def _smoothed_prob(self,
                       a: str,
                       b: str,
                       trans: dict[str, dict[str, float]],
                       counts: dict[str, float],
                       V: int) -> float:
        """Laplace smoothing para evitar prob=0."""
        c_ab = trans.get(a, {}).get(b, 0.0)
        c_a  = counts.get(a, 0.0)
        return (c_ab + self.alpha) / (c_a + self.alpha * V)

    def top_patterns(self, top_k: int = 10) -> list[dict[str, Any]]:
        """Patrones (A→B) más predictivos de cheater vs clean."""
        results = []
        for a, trans in self.cheater_trans.items():
            for b, c_ab in trans.items():
                p_ch  = c_ab / max(1.0, self.cheater_counts.get(a, 1.0))
                p_cl  = self.clean_trans.get(a, {}).get(b, 0.0) / max(1.0, self.clean_counts.get(a, 1.0))
                if p_ch > 0:
                    ratio = math.log((p_ch + 0.01) / (p_cl + 0.01))
                    results.append({
                        "from": a, "to": b,
                        "p_cheater": round(p_ch, 4),
                        "p_clean":   round(p_cl, 4),
                        "log_ratio": round(ratio, 4),
                        "count_cheater": c_ab,
                    })
        results.sort(key=lambda d: d["log_ratio"], reverse=True)
        return results[:top_k]

    # ── Persistencia ──────────────────────────────────────────────

    def to_json(self) -> str:
        return json.dumps({
            "cheater_trans": self.cheater_trans,
            "clean_trans": self.clean_trans,
            "cheater_counts": self.cheater_counts,
            "clean_counts": self.clean_counts,
            "alpha": self.alpha,
            "samples_observed": self.samples_observed,
        })

    @classmethod
    def from_json(cls, s: str) -> "TemporalPatternDetector":
        d = json.loads(s)
        m = cls()
        m.cheater_trans   = d.get("cheater_trans", {})
        m.clean_trans     = d.get("clean_trans", {})
        m.cheater_counts  = d.get("cheater_counts", {})
        m.clean_counts    = d.get("clean_counts", {})
        m.alpha           = d.get("alpha", 1.0)
        m.samples_observed = d.get("samples_observed", 0)
        return m


# ──────────────────────────────────────────────────────────────────────
#  Ensemble — combina LogReg + KNN + Temporal + Heuristic Prior
# ──────────────────────────────────────────────────────────────────────

@dataclass
class EnsembleResult:
    score: float                      # [0, 1] probabilidad de cheater
    confidence: float                 # [0, 1] cuán seguro está el ensemble
    components: dict[str, float]      # contribución de cada modelo
    component_scores: dict[str, float]
    top_features: list[tuple[str, float]]  # importancia firmada
    knn_neighbors: list[dict[str, Any]]
    temporal_llr: float
    explanation: str


def ensemble_predict(features: list[float],
                     sequence: list[str],
                     heuristic_score: float,
                     log_reg: LogisticRegression | None,
                     knn: KNNCheaterClassifier | None,
                     temporal: TemporalPatternDetector | None,
                     custom_weights: dict[str, float] | None = None
                     ) -> EnsembleResult:
    """
    Combina hasta 4 señales para producir un score final.

    Pesos adaptativos por defecto:
      - heuristic_score:    0.30 (baseline siempre disponible)
      - logreg:             0.35 (más peso si tiene >100 samples)
      - knn:                0.15 (más peso si tiene >20 examples balanceados)
      - temporal:           0.20 (más peso si tiene >50 sequences)

    Los pesos se ajustan dinámicamente: si un modelo no tiene suficientes
    samples para ser confiable, su peso se reduce y los otros se renormalizan.
    """
    base_weights = {
        "heuristic": 0.30,
        "logreg":    0.35,
        "knn":       0.15,
        "temporal":  0.20,
    }
    if custom_weights:
        base_weights.update(custom_weights)

    component_scores: dict[str, float] = {"heuristic": float(heuristic_score)}
    active_weights: dict[str, float] = {"heuristic": base_weights["heuristic"]}
    top_features: list[tuple[str, float]] = []
    neighbors: list[dict[str, Any]] = []
    temporal_llr = 0.0

    # LogReg
    if log_reg is not None and log_reg.samples_trained >= 20:
        try:
            p = log_reg.predict_proba(features)
            component_scores["logreg"] = p
            # Modular peso por # samples: hasta 100 samples = peso completo
            ramp = min(1.0, log_reg.samples_trained / 100.0)
            active_weights["logreg"] = base_weights["logreg"] * ramp
            top_features = log_reg.signed_importance(features, top_k=8)
        except Exception:
            pass

    # KNN
    if knn is not None and knn.size() >= knn.min_examples:
        try:
            r = knn.predict(features)
            component_scores["knn"] = r["score"]
            ramp = min(1.0, knn.size() / 30.0)
            active_weights["knn"] = base_weights["knn"] * ramp * (0.4 + 0.6 * r["confidence"])
            neighbors = r["neighbors"]
        except Exception:
            pass

    # Temporal
    if temporal is not None and temporal.samples_observed >= 10 and len(sequence) >= 2:
        try:
            r = temporal.score_sequence(sequence)
            component_scores["temporal"] = r["score"]
            ramp = min(1.0, temporal.samples_observed / 50.0)
            active_weights["temporal"] = base_weights["temporal"] * ramp
            temporal_llr = r["llr"]
        except Exception:
            pass

    # Normalizar pesos activos a sumar 1
    total_weight = sum(active_weights.values())
    if total_weight < 1e-9:
        active_weights = {"heuristic": 1.0}
        total_weight = 1.0
    normalized = {k: v / total_weight for k, v in active_weights.items()}

    # Score final
    final = 0.0
    for k, w in normalized.items():
        final += w * component_scores.get(k, 0.5)
    final = clamp(final, 0.0, 1.0)

    # Confianza: cuánto agreement hay entre componentes
    scores_arr = list(component_scores.values())
    if len(scores_arr) >= 2:
        mean_s = sum(scores_arr) / len(scores_arr)
        variance = sum((s - mean_s) ** 2 for s in scores_arr) / len(scores_arr)
        # 1 - stddev escalada (max stddev posible ≈ 0.5)
        agreement = 1.0 - min(1.0, math.sqrt(variance) / 0.5)
    else:
        agreement = 0.5
    component_count = len(component_scores)
    component_density = min(1.0, component_count / 4.0)
    confidence = round(0.4 * agreement + 0.6 * component_density, 4)

    # Explicación textual
    parts = []
    parts.append(f"Score ensemble: {final:.2f} (confianza {confidence:.2f}).")
    contribs_sorted = sorted(normalized.items(), key=lambda t: t[1], reverse=True)
    for k, w in contribs_sorted[:3]:
        if w > 0.05:
            parts.append(f"{k}: {component_scores[k]:.2f} (peso {w:.2f}).")
    if top_features:
        feat_str = ", ".join(f"{n}({s:+.2f})" for n, s in top_features[:3])
        parts.append(f"Top features: {feat_str}.")
    explanation = " ".join(parts)

    return EnsembleResult(
        score=round(final, 4),
        confidence=confidence,
        components=normalized,
        component_scores={k: round(v, 4) for k, v in component_scores.items()},
        top_features=top_features,
        knn_neighbors=neighbors,
        temporal_llr=temporal_llr,
        explanation=explanation,
    )


# ──────────────────────────────────────────────────────────────────────
#  Bootstrap: ejemplos sintéticos para arrancar el modelo con baseline
# ──────────────────────────────────────────────────────────────────────

def generate_bootstrap_dataset(feature_extractor,
                               n_cheaters: int = 200,
                               n_clean: int = 200,
                               n_borderline: int = 100,
                               seed: int = 1337
                               ) -> tuple[list[list[float]], list[float], list[float]]:
    """
    Genera ejemplos sintéticos balanceados con escenarios típicos para que
    el modelo arranque con baseline razonable.

    Devuelve (X, y, sample_weights). Los sample_weights son menores para
    ejemplos sintéticos (0.5) vs ejemplos reales (1.0+).

    `feature_extractor` debe ser callable que recibe un dict de evidence y
    devuelve un vector de features.
    """
    rng = random.Random(seed)
    X: list[list[float]] = []
    y: list[float] = []
    w: list[float] = []

    # ── Cheaters claros ────────────────────────────────────────────
    for _ in range(n_cheaters):
        ev = _synth_cheater(rng)
        X.append(feature_extractor(ev))
        y.append(1.0)
        w.append(0.5)

    # ── Limpios claros ─────────────────────────────────────────────
    for _ in range(n_clean):
        ev = _synth_clean(rng)
        X.append(feature_extractor(ev))
        y.append(0.0)
        w.append(0.5)

    # ── Borderline (clase difícil — 50/50, soft labels) ────────────
    for _ in range(n_borderline):
        ev, label = _synth_borderline(rng)
        X.append(feature_extractor(ev))
        y.append(label)
        w.append(0.3)

    return X, y, w


def _synth_cheater(rng: random.Random) -> dict[str, Any]:
    """Evidence típico de cheater (varios HIGH y CRITICAL en checks distintos)."""
    checks_pool = [
        "killaura_no_swing", "killaura_angle", "killaura_yaw_snap",
        "killaura_multi", "reach", "hit_through_wall", "autoclicker",
        "autoclicker_variance", "fly", "speed", "scaffold", "nofall",
    ]
    n_violations = rng.randint(3, 12)
    n_distinct = rng.randint(2, min(6, len(checks_pool)))
    chosen = rng.sample(checks_pool, n_distinct)
    violations = []
    for _ in range(n_violations):
        check = rng.choice(chosen)
        level_pool = ["MID", "HIGH", "HIGH", "CRITICAL"]
        violations.append({
            "check_name": check,
            "level": rng.choice(level_pool),
            "age_seconds": rng.uniform(5, 120),
        })
    return {
        "violations": violations,
        "account_age_hours": rng.choice([rng.uniform(0, 24),
                                         rng.uniform(48, 200),
                                         rng.uniform(1000, 5000)]),
        "playtime_hours": rng.uniform(0, 50),
        "prior_clean_scans": rng.choice([0, 0, 0, 1]),
        "scan_detected_hacks_recent": rng.random() < 0.4,
        "reports_in_chat": rng.randint(0, 8),
        "first_seen_now": rng.random() < 0.2,
        "current_score": rng.uniform(0.3, 0.95),
        "yaw_stability_extreme": rng.random() < 0.3,
        "hit_accept_rate": rng.uniform(0.85, 1.0),
        "avg_cps": rng.uniform(8, 22),
        "violations_cluster_density": rng.uniform(0.6, 1.0),
    }


def _synth_clean(rng: random.Random) -> dict[str, Any]:
    """Evidence típico de jugador limpio (pocas LOWs, history limpia)."""
    violations = []
    if rng.random() < 0.5:
        # Algunos limpios igual tienen 1-2 LOW (lag, sweep collateral, etc.)
        n = rng.randint(1, 3)
        for _ in range(n):
            violations.append({
                "check_name": rng.choice(["reach", "killaura_angle",
                                          "chat_spam", "cmd_spam",
                                          "killaura_multi", "speed"]),
                "level": "LOW",
                "age_seconds": rng.uniform(30, 300),
            })
    return {
        "violations": violations,
        "account_age_hours": rng.uniform(168, 50000),  # cuenta vieja
        "playtime_hours": rng.uniform(50, 1000),
        "prior_clean_scans": rng.randint(0, 8),
        "scan_detected_hacks_recent": False,
        "reports_in_chat": rng.randint(0, 1),
        "first_seen_now": False,
        "current_score": rng.uniform(0.0, 0.20),
        "yaw_stability_extreme": False,
        "hit_accept_rate": rng.uniform(0.3, 0.75),
        "avg_cps": rng.uniform(2, 9),
        "violations_cluster_density": rng.uniform(0.0, 0.3),
    }


def _synth_borderline(rng: random.Random) -> tuple[dict[str, Any], float]:
    """Edge cases ambiguos (cheater bobo en limpio o jugador pro con luck)."""
    is_cheater = rng.random() < 0.5
    label = 0.6 if is_cheater else 0.4  # soft label, no extremo
    violations = []
    n = rng.randint(2, 5)
    levels = ["LOW", "LOW", "MID", "HIGH"] if is_cheater else ["LOW", "LOW", "LOW", "MID"]
    pool = ["reach", "killaura_angle", "autoclicker", "speed",
            "killaura_multi", "fly", "chat_spam"]
    for _ in range(n):
        violations.append({
            "check_name": rng.choice(pool),
            "level": rng.choice(levels),
            "age_seconds": rng.uniform(20, 250),
        })
    return ({
        "violations": violations,
        "account_age_hours": rng.uniform(24, 500),
        "playtime_hours": rng.uniform(10, 200),
        "prior_clean_scans": rng.randint(0, 3),
        "scan_detected_hacks_recent": is_cheater and rng.random() < 0.25,
        "reports_in_chat": rng.randint(0, 3),
        "first_seen_now": rng.random() < 0.3,
        "current_score": rng.uniform(0.15, 0.55),
        "yaw_stability_extreme": is_cheater and rng.random() < 0.3,
        "hit_accept_rate": rng.uniform(0.6, 0.92),
        "avg_cps": rng.uniform(5, 14),
        "violations_cluster_density": rng.uniform(0.2, 0.6),
    }, label)
