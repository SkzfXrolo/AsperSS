"""
Clasificador autónomo para predicción hack/clean.
Aprende solo mediante tres mecanismos que no requieren input humano:

  1. Random Forest supervisado — entrena con veredictos humanos SI existen,
     y con pseudo-labels auto-generados cuando no los hay.

  2. Isolation Forest no supervisado — detecta anomalías estadísticas en
     TODOS los scans sin necesitar ninguna etiqueta.

  3. Auto-etiquetado por consenso — cuando el score heurístico es extremo
     (≥88 o ≤8) y múltiples señales coinciden, genera pseudo-labels.

Ensemble final: 50% heurístico + 30% RF + 20% Isolation Forest.
"""
import os
import json
import time

MODEL_PATH = os.path.join(
    os.environ.get('APPDATA', os.path.dirname(__file__)),
    'ASPERSProjectsSS', 'hack_classifier.pkl'
)
ISO_MODEL_PATH = os.path.join(
    os.environ.get('APPDATA', os.path.dirname(__file__)),
    'ASPERSProjectsSS', 'isolation_forest.pkl'
)

_ALERT_MAP = {'CRITICAL': 4, 'MUY_SOSPECHOSO': 3, 'SOSPECHOSO': 2, 'POCO_SOSPECHOSO': 1, 'NORMAL': 0}
_CAT_MAP = {
    'GHOST_CLIENT': 10, 'JAVA_INJECTION': 9, 'EVASION': 8, 'FORENSE': 7,
    'PROCESO': 6, 'MACRO': 5, 'RED': 4, 'SISTEMA': 3, 'ARCHIVO': 2, 'OTHER': 1,
}

# Thresholds for autonomous auto-labeling
_AUTO_HACK_THRESHOLD  = 88   # heuristic score ≥ this → auto-label hack
_AUTO_CLEAN_THRESHOLD = 8    # heuristic score ≤ this → auto-label clean


def _extract_finding_features(row):
    """4 features per individual finding."""
    if hasattr(row, 'keys'):
        d = dict(row)
    elif isinstance(row, dict):
        d = row
    else:
        d = {
            'alert_level':          row[3] if len(row) > 3 else '',
            'issue_category':       row[2] if len(row) > 2 else '',
            'confidence':           row[5] if len(row) > 5 else 0.5,
            'obfuscation_detected': row[6] if len(row) > 6 else 0,
        }
    return [
        _ALERT_MAP.get(str(d.get('alert_level', '')).upper(), 0),
        _CAT_MAP.get(str(d.get('issue_category', '')).upper(), 1),
        float(d.get('confidence', 0.5) or 0.5),
        int(bool(d.get('obfuscation_detected', 0))),
    ]


# Keep old name as alias so existing callers (app.py) don't break
_extract_features = _extract_finding_features


def _extract_scan_features(rows):
    """8 aggregate features per scan (used for RF and Isolation Forest).
    rows: list of finding dicts/rows for a single scan.
    """
    if not rows:
        return [0, 0, 0, 0.5, 0, 0, 0, 0]

    alert_nums   = [_ALERT_MAP.get(str((r.get('alert_level') if isinstance(r, dict) else r[3] if len(r) > 3 else '')).upper(), 0) for r in rows]
    cat_nums     = [_CAT_MAP.get(str((r.get('issue_category') if isinstance(r, dict) else r[2] if len(r) > 2 else '')).upper(), 1) for r in rows]
    confs        = [float((r.get('confidence') if isinstance(r, dict) else r[5] if len(r) > 5 else 0.5) or 0.5) for r in rows]
    obfuscs      = [int(bool(r.get('obfuscation_detected') if isinstance(r, dict) else r[6] if len(r) > 6 else 0)) for r in rows]

    total          = len(rows)
    critical_count = sum(1 for a in alert_nums if a >= 4)
    max_alert      = max(alert_nums)
    avg_conf       = sum(confs) / total
    obfusc_count   = sum(obfuscs)
    category_div   = len(set(cat_nums))
    high_risk      = sum(1 for a in alert_nums if a >= 3)
    top_cat        = max(cat_nums)

    return [total, critical_count, max_alert, avg_conf, obfusc_count, category_div, high_risk, top_cat]


class HackClassifier:
    def __init__(self):
        self._model      = None   # Random Forest (supervised)
        self._iso_model  = None   # Isolation Forest (unsupervised)
        self._trained_on = 0
        self._iso_trained_on = 0
        self._load()

    # ------------------------------------------------------------------ #
    #  Persistence                                                         #
    # ------------------------------------------------------------------ #

    def _load(self):
        try:
            import joblib
            if os.path.isfile(MODEL_PATH):
                data = joblib.load(MODEL_PATH)
                self._model      = data.get('model')
                self._trained_on = data.get('trained_on', 0)
                print(f"[ML] RF cargado ({self._trained_on} muestras)")
            if os.path.isfile(ISO_MODEL_PATH):
                data = joblib.load(ISO_MODEL_PATH)
                self._iso_model      = data.get('model')
                self._iso_trained_on = data.get('trained_on', 0)
                print(f"[ML] IsoForest cargado ({self._iso_trained_on} scans)")
        except Exception as e:
            print(f"[ML] Error cargando modelo: {e}")

    # ------------------------------------------------------------------ #
    #  Supervised RF training (human verdicts + auto-labels)              #
    # ------------------------------------------------------------------ #

    def train(self, cursor):
        """Entrena RF con veredictos humanos + pseudo-labels autónomos.
        No requiere inputs humanos si hay suficientes auto-labels.
        """
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.calibration import CalibratedClassifierCV
            from sklearn.model_selection import cross_val_score
            import joblib, numpy as np
        except ImportError:
            return {'trained': False, 'error': 'scikit-learn no instalado'}

        try:
            # Human verdicts (highest trust)
            cursor.execute('''
                SELECT sr.alert_level, sr.issue_category, sr.confidence,
                       sr.obfuscation_detected, s.verdict,
                       s.id as scan_id
                FROM scan_results sr
                JOIN scans s ON sr.scan_id = s.id
                WHERE s.verdict IN ('hack', 'clean')
                  AND sr.alert_level IS NOT NULL
                LIMIT 5000
            ''')
            human_rows = cursor.fetchall() or []
        except Exception as e:
            human_rows = []

        try:
            # Auto-labels generated by the autonomous pipeline
            cursor.execute('''
                SELECT sr.alert_level, sr.issue_category, sr.confidence,
                       sr.obfuscation_detected, al.auto_verdict,
                       al.scan_id
                FROM auto_labels al
                JOIN scan_results sr ON sr.scan_id = al.scan_id
                WHERE al.confidence >= 0.80
                  AND sr.alert_level IS NOT NULL
                LIMIT 5000
            ''')
            auto_rows = cursor.fetchall() or []
        except Exception:
            auto_rows = []

        X, y = [], []

        for row in human_rows:
            verdict = str(row[4] if not hasattr(row, 'keys') else row.get('verdict', ''))
            if verdict not in ('hack', 'clean'):
                continue
            X.append(_extract_finding_features(row))
            y.append(1 if verdict == 'hack' else 0)

        # Auto-labels weighted at 0.7 — added twice if confidence >= 0.92 to increase weight
        for row in auto_rows:
            verdict = str(row[4] if not hasattr(row, 'keys') else row.get('auto_verdict', ''))
            if verdict not in ('hack', 'clean'):
                continue
            feat = _extract_finding_features(row)
            label = 1 if verdict == 'hack' else 0
            X.append(feat)
            y.append(label)

        hack_count  = sum(y)
        clean_count = len(y) - hack_count

        if hack_count < 5 or clean_count < 5:
            return {
                'trained': False,
                'error': f'Insuficientes muestras: {hack_count} hacks, {clean_count} limpios (mín 5 c/u)',
                'human_samples': len(human_rows),
                'auto_samples': len(auto_rows),
            }

        import numpy as np
        X_arr = np.array(X, dtype=float)
        y_arr = np.array(y)

        base_clf = RandomForestClassifier(
            n_estimators=120, max_depth=7, random_state=42,
            class_weight='balanced', n_jobs=-1,
        )
        cv_folds = min(5, hack_count, clean_count)
        try:
            scores = cross_val_score(base_clf, X_arr, y_arr, cv=cv_folds, scoring='accuracy')
            accuracy = round(float(scores.mean()), 4)
        except Exception:
            accuracy = 0.0

        cal_cv = min(3, hack_count, clean_count)
        clf = CalibratedClassifierCV(base_clf, method='sigmoid', cv=cal_cv)
        clf.fit(X_arr, y_arr)
        self._model      = clf
        self._trained_on = len(y)

        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        import joblib
        joblib.dump({'model': clf, 'trained_on': len(y), 'accuracy': accuracy, 'calibrated': True}, MODEL_PATH)
        print(f"[ML] RF entrenado: {len(y)} muestras ({len(human_rows)} humanas + {len(auto_rows)} auto), acc={accuracy:.3f}")
        return {
            'trained': True, 'samples': len(y),
            'human_samples': len(human_rows), 'auto_samples': len(auto_rows),
            'hack_count': hack_count, 'clean_count': clean_count,
            'accuracy': accuracy, 'calibrated': True,
        }

    # ------------------------------------------------------------------ #
    #  Unsupervised Isolation Forest                                       #
    # ------------------------------------------------------------------ #

    def train_isolation_forest(self, cursor):
        """Entrena Isolation Forest con TODOS los scans, sin necesitar etiquetas.
        Detecta anomalías estadísticas — scans raros respecto a la mayoría.
        """
        try:
            from sklearn.ensemble import IsolationForest
            import joblib, numpy as np
        except ImportError:
            return {'trained': False, 'error': 'scikit-learn no instalado'}

        try:
            cursor.execute('''
                SELECT s.id,
                       COUNT(sr.id)                                    AS total,
                       SUM(CASE WHEN sr.alert_level='CRITICAL' THEN 1 ELSE 0 END)        AS crit,
                       MAX(CASE sr.alert_level
                               WHEN 'CRITICAL'        THEN 4
                               WHEN 'MUY_SOSPECHOSO'  THEN 3
                               WHEN 'SOSPECHOSO'      THEN 2
                               WHEN 'POCO_SOSPECHOSO' THEN 1
                               ELSE 0 END)                             AS max_alert,
                       AVG(COALESCE(sr.confidence, 0.5))              AS avg_conf,
                       SUM(CASE WHEN sr.obfuscation_detected THEN 1 ELSE 0 END) AS obfusc,
                       COUNT(DISTINCT sr.issue_category)              AS cat_div,
                       SUM(CASE WHEN sr.alert_level IN ('CRITICAL','MUY_SOSPECHOSO') THEN 1 ELSE 0 END) AS high_risk
                FROM scans s
                JOIN scan_results sr ON sr.scan_id = s.id
                GROUP BY s.id
                HAVING COUNT(sr.id) > 0
                LIMIT 10000
            ''')
            rows = cursor.fetchall() or []
        except Exception as e:
            return {'trained': False, 'error': f'Query error: {e}'}

        if len(rows) < 30:
            return {'trained': False, 'error': f'Solo {len(rows)} scans con hallazgos (mín 30)'}

        X = []
        for r in rows:
            if hasattr(r, 'keys'):
                d = dict(r)
                X.append([
                    float(d.get('total', 0) or 0),
                    float(d.get('crit', 0) or 0),
                    float(d.get('max_alert', 0) or 0),
                    float(d.get('avg_conf', 0.5) or 0.5),
                    float(d.get('obfusc', 0) or 0),
                    float(d.get('cat_div', 0) or 0),
                    float(d.get('high_risk', 0) or 0),
                ])
            else:
                X.append([float(v or 0) for v in r[1:8]])

        X_arr = np.array(X, dtype=float)

        iso = IsolationForest(
            n_estimators=200,
            contamination=0.08,   # assume ~8% of scans are hacks
            random_state=42,
            n_jobs=-1,
        )
        iso.fit(X_arr)
        self._iso_model      = iso
        self._iso_trained_on = len(X)

        os.makedirs(os.path.dirname(ISO_MODEL_PATH), exist_ok=True)
        import joblib
        joblib.dump({'model': iso, 'trained_on': len(X)}, ISO_MODEL_PATH)
        print(f"[ML] IsoForest entrenado: {len(X)} scans")
        return {'trained': True, 'scans': len(X)}

    # ------------------------------------------------------------------ #
    #  Autonomous auto-labeling pipeline                                  #
    # ------------------------------------------------------------------ #

    def generate_auto_labels(self, cursor):
        """Lee scans sin veredicto humano y genera pseudo-labels cuando
        el score heurístico es extremo Y el Isolation Forest confirma.
        Inserta/actualiza la tabla auto_labels.
        """
        _ensure_auto_labels_table(cursor)

        try:
            cursor.execute('''
                SELECT s.id, s.risk_score
                FROM scans s
                WHERE s.verdict IS NULL
                  AND s.risk_score IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM auto_labels al WHERE al.scan_id = s.id)
                ORDER BY s.id DESC
                LIMIT 500
            ''')
            candidates = cursor.fetchall() or []
        except Exception as e:
            return {'labeled': 0, 'error': str(e)}

        labeled = 0
        for row in candidates:
            scan_id    = row[0] if not hasattr(row, 'keys') else row.get('id')
            risk_score = row[1] if not hasattr(row, 'keys') else row.get('risk_score')
            if risk_score is None:
                continue

            if risk_score >= _AUTO_HACK_THRESHOLD:
                verdict    = 'hack'
                confidence = min(0.99, 0.80 + (risk_score - _AUTO_HACK_THRESHOLD) * 0.01)
            elif risk_score <= _AUTO_CLEAN_THRESHOLD:
                verdict    = 'clean'
                confidence = min(0.99, 0.80 + (_AUTO_CLEAN_THRESHOLD - risk_score) * 0.01)
            else:
                continue

            # Boost confidence if Isolation Forest also flags it
            if self._iso_model is not None:
                iso_score = self._iso_score_for_scan(cursor, scan_id)
                if iso_score is not None:
                    if verdict == 'hack'  and iso_score < 0:    # negative = anomaly
                        confidence = min(0.99, confidence + 0.08)
                    elif verdict == 'clean' and iso_score >= 0:  # positive = normal
                        confidence = min(0.99, confidence + 0.08)

            try:
                cursor.execute('''
                    INSERT INTO auto_labels (scan_id, auto_verdict, confidence, created_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (scan_id) DO UPDATE
                        SET auto_verdict = EXCLUDED.auto_verdict,
                            confidence   = EXCLUDED.confidence,
                            created_at   = NOW()
                ''', (scan_id, verdict, confidence))
                labeled += 1
            except Exception:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO auto_labels (scan_id, auto_verdict, confidence, created_at)
                        VALUES (?, ?, ?, datetime('now'))
                    ''', (scan_id, verdict, confidence))
                    labeled += 1
                except Exception:
                    pass

        print(f"[ML] Auto-labels generados: {labeled} nuevos")
        return {'labeled': labeled, 'candidates': len(candidates)}

    def _iso_score_for_scan(self, cursor, scan_id):
        """Calcula el score de anomalía de Isolation Forest para un scan."""
        try:
            cursor.execute('''
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN alert_level='CRITICAL' THEN 1 ELSE 0 END) AS crit,
                       MAX(CASE alert_level
                               WHEN 'CRITICAL' THEN 4 WHEN 'MUY_SOSPECHOSO' THEN 3
                               WHEN 'SOSPECHOSO' THEN 2 WHEN 'POCO_SOSPECHOSO' THEN 1
                               ELSE 0 END) AS max_alert,
                       AVG(COALESCE(confidence, 0.5)) AS avg_conf,
                       SUM(CASE WHEN obfuscation_detected THEN 1 ELSE 0 END) AS obfusc,
                       COUNT(DISTINCT issue_category) AS cat_div,
                       SUM(CASE WHEN alert_level IN ('CRITICAL','MUY_SOSPECHOSO') THEN 1 ELSE 0 END) AS high_risk
                FROM scan_results WHERE scan_id = %s
            ''', (scan_id,))
            r = cursor.fetchone()
        except Exception:
            try:
                cursor.execute('''
                    SELECT COUNT(*), SUM(CASE WHEN alert_level='CRITICAL' THEN 1 ELSE 0 END),
                           MAX(CASE alert_level WHEN 'CRITICAL' THEN 4 WHEN 'MUY_SOSPECHOSO' THEN 3
                               WHEN 'SOSPECHOSO' THEN 2 ELSE 0 END),
                           AVG(COALESCE(confidence, 0.5)), 0, COUNT(DISTINCT issue_category), 0
                    FROM scan_results WHERE scan_id = ?
                ''', (scan_id,))
                r = cursor.fetchone()
            except Exception:
                return None

        if not r:
            return None

        import numpy as np
        feats = np.array([[
            float(r[0] or 0), float(r[1] or 0), float(r[2] or 0),
            float(r[3] or 0.5), float(r[4] or 0), float(r[5] or 0), float(r[6] or 0),
        ]], dtype=float)
        scores = self._iso_model.score_samples(feats)
        return float(scores[0])

    # ------------------------------------------------------------------ #
    #  Hash consensus learning                                            #
    # ------------------------------------------------------------------ #

    def learn_hash_consensus(self, cursor):
        """Si el mismo file_hash aparece en ≥3 scans y la mayoría tienen
        risk_score alto, lo añade a learned_hashes automáticamente.
        """
        promoted = 0
        try:
            cursor.execute('''
                SELECT sr.file_hash,
                       COUNT(DISTINCT s.id)          AS appearances,
                       AVG(COALESCE(s.risk_score, 50)) AS avg_score,
                       SUM(CASE WHEN COALESCE(s.risk_score,50) >= 70 THEN 1 ELSE 0 END) AS high_risk_count
                FROM scan_results sr
                JOIN scans s ON sr.scan_id = s.id
                WHERE sr.file_hash IS NOT NULL
                  AND sr.file_hash != ''
                GROUP BY sr.file_hash
                HAVING COUNT(DISTINCT s.id) >= 3
            ''')
            hash_stats = cursor.fetchall() or []
        except Exception as e:
            return {'promoted': 0, 'error': str(e)}

        for row in hash_stats:
            if hasattr(row, 'keys'):
                d = dict(row)
                fhash       = d.get('file_hash')
                appearances = int(d.get('appearances', 0))
                avg_score   = float(d.get('avg_score', 50))
                hr_count    = int(d.get('high_risk_count', 0))
            else:
                fhash, appearances, avg_score, hr_count = row[0], int(row[1]), float(row[2]), int(row[3])

            if not fhash:
                continue

            # Consensus: ≥70% of appearances are high-risk AND average score ≥ 72
            if appearances >= 3 and hr_count / appearances >= 0.70 and avg_score >= 72:
                try:
                    cursor.execute('''
                        INSERT INTO learned_hashes (file_hash, is_hack, confirmed_count, last_seen)
                        VALUES (%s, TRUE, %s, NOW())
                        ON CONFLICT (file_hash) DO UPDATE
                            SET confirmed_count = learned_hashes.confirmed_count + 1,
                                last_seen = NOW()
                    ''', (fhash, appearances))
                    promoted += 1
                except Exception:
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO learned_hashes (file_hash, is_hack, confirmed_count)
                            VALUES (?, 1, ?)
                        ''', (fhash, appearances))
                        promoted += 1
                    except Exception:
                        pass

        if promoted:
            print(f"[ML] Hash consensus: {promoted} hashes promovidos a learned_hashes")
        return {'promoted': promoted}

    # ------------------------------------------------------------------ #
    #  Inference                                                          #
    # ------------------------------------------------------------------ #

    def predict(self, features: dict) -> dict:
        """Predice hack/clean para un hallazgo individual (RF)."""
        if self._model is None:
            return {'label': None, 'confidence': None, 'available': False}
        try:
            import numpy as np
            X = np.array([_extract_finding_features(features)], dtype=float)
            proba = self._model.predict_proba(X)[0]
            label = 'hack' if proba[1] > 0.5 else 'clean'
            return {
                'label':       label,
                'confidence':  round(float(max(proba)), 4),
                'hack_prob':   round(float(proba[1]), 4),
                'available':   True,
                'trained_on':  self._trained_on,
            }
        except Exception as e:
            return {'label': None, 'confidence': None, 'available': False, 'error': str(e)}

    def predict_iso(self, scan_feature_row: list) -> dict:
        """Score de anomalía del Isolation Forest para un scan completo.
        scan_feature_row: [total, crit, max_alert, avg_conf, obfusc, cat_div, high_risk]
        Retorna {'anomaly': bool, 'score': float (-1..0), 'available': bool}
        """
        if self._iso_model is None:
            return {'anomaly': False, 'score': 0.0, 'available': False}
        try:
            import numpy as np
            X = np.array([scan_feature_row[:7]], dtype=float)
            score  = float(self._iso_model.score_samples(X)[0])
            label  = self._iso_model.predict(X)[0]   # -1=anomaly, 1=normal
            return {
                'anomaly':   label == -1,
                'score':     round(score, 4),
                'available': True,
            }
        except Exception as e:
            return {'anomaly': False, 'score': 0.0, 'available': False, 'error': str(e)}

    @property
    def is_available(self):
        return self._model is not None

    @property
    def iso_available(self):
        return self._iso_model is not None


# ------------------------------------------------------------------ #
#  DB helper                                                          #
# ------------------------------------------------------------------ #

def _ensure_auto_labels_table(cursor):
    """Crea auto_labels si no existe (PostgreSQL o SQLite)."""
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_labels (
                id           SERIAL PRIMARY KEY,
                scan_id      INTEGER NOT NULL UNIQUE,
                auto_verdict VARCHAR(10) NOT NULL,
                confidence   FLOAT NOT NULL DEFAULT 0.8,
                created_at   TIMESTAMP DEFAULT NOW()
            )
        ''')
    except Exception:
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS auto_labels (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id      INTEGER NOT NULL UNIQUE,
                    auto_verdict TEXT NOT NULL,
                    confidence   REAL NOT NULL DEFAULT 0.8,
                    created_at   TEXT DEFAULT (datetime('now'))
                )
            ''')
        except Exception:
            pass


# ------------------------------------------------------------------ #
#  Singleton                                                          #
# ------------------------------------------------------------------ #

_classifier = None

def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = HackClassifier()
    return _classifier
