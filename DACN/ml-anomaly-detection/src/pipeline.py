"""One chronological detection pipeline shared by CLI, HTTP and Streamlit."""
from __future__ import annotations
from dataclasses import dataclass
import json
import numpy as np
import pandas as pd
from .data_prep import load_timeseries
from .models import MODEL_NAMES, build_feature_matrix, evaluate_predictions, fit_models

@dataclass
class DetectionRun:
    frame: pd.DataFrame
    predictions: pd.DataFrame
    metrics: dict
    metadata: dict

    def summary(self) -> dict:
        records = json.loads(self.predictions.to_json(orient='records', date_format='iso'))
        anomalies = {name: [row for row in records if row[f'{name}_prediction'] == -1]
                     for name in self.metadata['model_names']}
        return {'metadata': self.metadata, 'metrics': self.metrics,
                'anomalies': anomalies, 'predictions': records}

    def export_csv(self) -> bytes:
        return self.predictions.to_csv(index=False).encode('utf-8-sig')


def run_detection(source, timestamp_col='timestamp', value_col='value', label_col=None,
                  train_fraction=.7, contamination=.01, model_names=None,
                  include_time=False, split_index=None) -> DetectionRun:
    """Fit only past rows; predict only subsequent rows. Labels are opt-in, {-1,1}."""
    names = list(MODEL_NAMES if model_names is None else [model_names] if isinstance(model_names, str) else model_names)
    if not names or any(not isinstance(name, str) or name not in MODEL_NAMES for name in names) or len(set(names)) != len(names):
        raise ValueError('Select unique algorithms from: ' + ', '.join(MODEL_NAMES))
    numeric_types = (int, float, np.integer, np.floating)
    if isinstance(train_fraction, bool) or not isinstance(train_fraction, numeric_types) or not np.isfinite(train_fraction) or not 0 < train_fraction < 1:
        raise ValueError('train_fraction must lie in (0, 1)')
    if isinstance(contamination, bool) or not isinstance(contamination, numeric_types) or not np.isfinite(contamination) or not 0 < contamination <= .5:
        raise ValueError('contamination must lie in (0, 0.5]')
    frame = load_timeseries(source, timestamp_col, value_col)
    if value_col is None:
        value_col = frame.attrs.get('value_col')
        if value_col is None:
            from .data_prep import database_metric_columns
            value_col = database_metric_columns(frame)[0]
    if timestamp_col == value_col or (label_col and label_col in (timestamp_col, value_col)):
        raise ValueError('Timestamp, value and label columns must be distinct')
    output_columns = {f'{name}_{suffix}' for name in names for suffix in ('prediction', 'score')}
    if any(column in output_columns for column in (timestamp_col, value_col, label_col)):
        raise ValueError('Selected input columns conflict with generated prediction/score names; rename them before analysis')
    if label_col:
        if label_col not in frame:
            raise ValueError(f'Missing label column: {label_col}')
        labels = pd.to_numeric(frame[label_col], errors='coerce')
        has_boolean_labels = frame[label_col].map(lambda value: isinstance(value, (bool, np.bool_))).any()
        if has_boolean_labels or labels.isna().any() or not labels.isin([-1, 1]).all():
            raise ValueError('Labels must be explicit -1 (anomaly) or 1 (normal), without missing values')
        frame[label_col] = labels.astype(int)
    if split_index is not None and (isinstance(split_index, bool) or not isinstance(split_index, (int, np.integer))):
        raise ValueError('split_index must be an integer')
    split = int(len(frame) * train_fraction) if split_index is None else int(split_index)
    if split < 3 or split >= len(frame):
        raise ValueError('Need at least 3 training rows and 1 test row; adjust split or provide more data')
    features = build_feature_matrix(frame, value_col, timestamp_col, include_time=include_time)
    results = fit_models(features.iloc[:split], features.iloc[split:],
                         contamination=contamination, random_state=42, model_names=names)
    cols = [timestamp_col, value_col] + ([label_col] if label_col else [])
    predictions = frame.iloc[split:][cols].copy().reset_index(drop=True)
    metrics = {}
    for name, result in results.items():
        predictions[f'{name}_prediction'] = result.predictions
        predictions[f'{name}_score'] = result.scores
        if label_col:
            metrics[name] = evaluate_predictions(predictions[label_col], result.predictions)
    warnings = []
    if frame.attrs.get('cleaning', {}).get('dropped_rows', 0):
        warnings.append('Rows with missing, nonnumeric or infinite metric values were removed before the chronological split; see cleaning counts.')
    if len(frame) < 100:
        warnings.append('Small dataset: this run verifies functionality and cannot establish general detection quality.')
    if not label_col:
        warnings.append('No ground-truth labels selected: precision, recall and F1 are not computed.')
    elif (predictions[label_col] == -1).sum() == 0:
        warnings.append('Test labels contain no anomalies: recall/F1 cannot support a detection-quality conclusion.')
    if include_time:
        warnings.append('All selected models use metric and calendar features. MAD combines their maximum absolute robust z-score; rare calendar values can trigger alerts.')
    metadata = {
        'rows': len(frame), 'train_rows': split, 'test_rows': len(frame)-split,
        'split_index': split, 'train_fraction': split/len(frame),
        'timestamp_col': timestamp_col, 'value_col': value_col, 'label_col': label_col,
        'model_names': names, 'features': list(features.columns),
        'contamination': contamination, 'random_state': 42, 'warnings': warnings,
        'cleaning': frame.attrs.get('cleaning', {}),
        'parameters': {name: getattr(result, 'parameters', {}) for name, result in results.items()},
        'timings': {name: {'train_seconds': getattr(result, 'train_seconds', 0.),
                           'predict_seconds': getattr(result, 'predict_seconds', 0.)}
                    for name, result in results.items()},
        'label_policy': 'explicit point labels (-1 anomaly, 1 normal)' if label_col else 'unlabeled',
        'scope': 'Offline CSV metric analysis; no direct DBMS connection or real-time monitoring.'
    }
    return DetectionRun(frame, predictions, metrics, metadata)
