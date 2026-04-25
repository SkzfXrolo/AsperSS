"""
P3 #1 — Clasificador Random Forest para predicción hack/clean.
Entrena con feedbacks acumulados en staff_feedback + scan_results.
Exporta modelo como .pkl en APPDATA o directorio del servidor.

Uso:
    from ml_classifier import HackClassifier
    clf = HackClassifier()
    clf.train(cursor)                    # reentrena
    pred = clf.predict(features_dict)   # {'label': 'hack'/'clean', 'confidence': 0.87}
"""
import os
import json

MODEL_PATH = os.path.join(
    os.environ.get('APPDATA', os.path.dirname(__file__)),
    'ASPERSProjectsSS', 'hack_classifier.pkl'
)

_ALERT_MAP = {'CRITICAL': 4, 'MUY_SOSPECHOSO': 3, 'SOSPECHOSO': 2, 'POCO_SOSPECHOSO': 1, 'NORMAL': 0}
_CAT_MAP   = {
    'GHOST_CLIENT': 10, 'JAVA_INJECTION': 9, 'EVASION': 8, 'FORENSE': 7,
    'PROCESO': 6, 'MACRO': 5, 'RED': 4, 'SISTEMA': 3, 'ARCHIVO': 2, 'OTHER': 1,
}


def _extract_features(row):
    """Extrae vector de features desde una fila de scan_results o dict."""
    if hasattr(row, 'keys'):
        d = dict(row)
    elif isinstance(row, dict):
        d = row
    else:
        d = {
            'alert_level': row[3] if len(row) > 3 else '',
            'issue_category': row[2] if len(row) > 2 else '',
            'confidence': row[5] if len(row) > 5 else 0.5,
            'obfuscation_detected': row[6] if len(row) > 6 else 0,
        }
    alert_num = _ALERT_MAP.get(str(d.get('alert_level', '')).upper(), 0)
    cat_num   = _CAT_MAP.get(str(d.get('issue_category', '')).upper(), 1)
    conf      = float(d.get('confidence', 0.5) or 0.5)
    obfusc    = int(bool(d.get('obfuscation_detected', 0)))
    return [alert_num, cat_num, conf, obfusc]


class HackClassifier:
    def __init__(self):
        self._model = None
        self._trained_on = 0
        self._load()

    def _load(self):
        try:
            import joblib
            if os.path.isfile(MODEL_PATH):
                data = joblib.load(MODEL_PATH)
                self._model       = data.get('model')
                self._trained_on  = data.get('trained_on', 0)
                print(f"[ML] Modelo cargado ({self._trained_on} muestras)")
        except Exception as e:
            print(f"[ML] No se pudo cargar modelo: {e}")

    def train(self, cursor):
        """Reentrena el clasificador con todos los feedbacks disponibles.
        Requiere al menos 20 muestras (10 hack, 10 clean).
        Retorna {'trained': bool, 'samples': int, 'accuracy': float}.
        """
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import cross_val_score
            import joblib, numpy as np
        except ImportError:
            return {'trained': False, 'error': 'scikit-learn no instalado'}

        try:
            # Recolectar muestras: scan_results + veredicto del scan
            cursor.execute('''
                SELECT sr.alert_level, sr.issue_category, sr.confidence,
                       sr.obfuscation_detected, s.verdict
                FROM scan_results sr
                JOIN scans s ON sr.scan_id = s.id
                WHERE s.verdict IN ('hack', 'clean')
                  AND sr.alert_level IS NOT NULL
                LIMIT 5000
            ''')
            rows = cursor.fetchall() or []
        except Exception as e:
            return {'trained': False, 'error': f'Query error: {e}'}

        X, y = [], []
        for row in rows:
            verdict = str(row[4] if not hasattr(row, 'keys') else row.get('verdict', ''))
            if verdict not in ('hack', 'clean'):
                continue
            X.append(_extract_features(row))
            y.append(1 if verdict == 'hack' else 0)

        hack_count  = sum(y)
        clean_count = len(y) - hack_count
        if hack_count < 5 or clean_count < 5:
            return {'trained': False, 'error': f'Insuficientes muestras: {hack_count} hacks, {clean_count} limpios (mín 5 cada uno)'}

        X_arr = np.array(X, dtype=float)
        y_arr = np.array(y)

        clf = RandomForestClassifier(
            n_estimators=100, max_depth=6, random_state=42,
            class_weight='balanced', n_jobs=-1
        )
        # Cross-validation para medir accuracy
        try:
            scores = cross_val_score(clf, X_arr, y_arr, cv=min(5, hack_count, clean_count), scoring='accuracy')
            accuracy = round(float(scores.mean()), 4)
        except Exception:
            accuracy = 0.0

        clf.fit(X_arr, y_arr)
        self._model = clf
        self._trained_on = len(y)

        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump({'model': clf, 'trained_on': len(y), 'accuracy': accuracy}, MODEL_PATH)
        print(f"[ML] Entrenado: {len(y)} muestras, accuracy={accuracy:.3f}")
        return {
            'trained': True, 'samples': len(y),
            'hack_count': hack_count, 'clean_count': clean_count,
            'accuracy': accuracy,
        }

    def predict(self, features: dict) -> dict:
        """Predice hack/clean para un hallazgo individual.
        features: {'alert_level', 'issue_category', 'confidence', 'obfuscation_detected'}
        """
        if self._model is None:
            return {'label': None, 'confidence': None, 'available': False}
        try:
            import numpy as np
            X = np.array([_extract_features(features)], dtype=float)
            proba = self._model.predict_proba(X)[0]
            label = 'hack' if proba[1] > 0.5 else 'clean'
            return {
                'label': label,
                'confidence': round(float(max(proba)), 4),
                'hack_prob': round(float(proba[1]), 4),
                'available': True,
                'trained_on': self._trained_on,
            }
        except Exception as e:
            return {'label': None, 'confidence': None, 'available': False, 'error': str(e)}

    @property
    def is_available(self):
        return self._model is not None


# Singleton global para la app
_classifier = None

def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = HackClassifier()
    return _classifier
