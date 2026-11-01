"""Download pinned NAB evidence, run real experiments, save metrics and figures."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import sys
import zipfile
import requests
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'DACN' / 'ml-anomaly-detection'
sys.path.insert(0, str(PROJECT))
from src.pipeline import run_detection

RESULTS = ROOT / 'experiments' / 'results'
DATA = PROJECT / 'data'
KEY = 'realAWSCloudwatch/ec2_cpu_utilization_24ae8d.csv'

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def fetch(url):
    response = requests.get(url, timeout=(20, 120))
    response.raise_for_status()
    return response

def prepare_data():
    provenance_path = DATA / 'nab_provenance.json'
    if provenance_path.exists():
        info = json.loads(provenance_path.read_text(encoding='utf-8'))
        raw = DATA / 'ec2_cpu_utilization.csv'
        if sha(raw.read_bytes()) != info['sha256']:
            raise ValueError('Downloaded dataset hash differs from recorded provenance')
        return info
    commit = fetch('https://api.github.com/repos/numenta/NAB/commits/master').json()['sha']
    base = f'https://raw.githubusercontent.com/numenta/NAB/{commit}'
    raw = fetch(f'{base}/data/{KEY}').content
    label_bytes = fetch(f'{base}/labels/combined_labels.json').content
    license_bytes = fetch(f'{base}/LICENSE.txt').content
    frame = pd.read_csv(io.BytesIO(raw))
    labels = json.loads(label_bytes)[KEY]
    if len(frame) != 4032 or frame['timestamp'].duplicated().any():
        raise ValueError('Unexpected NAB dataset structure')
    if not set(labels).issubset(set(frame['timestamp'])):
        raise ValueError('Source point labels do not match dataset timestamps')
    frame['is_anomaly'] = np.where(frame['timestamp'].isin(labels), -1, 1)
    (DATA / 'ec2_cpu_utilization.csv').write_bytes(raw)
    (DATA / 'nab_combined_labels.json').write_bytes(label_bytes)
    (DATA / 'NAB_LICENSE.txt').write_bytes(license_bytes)
    frame.to_csv(DATA / 'nab_cpu_labeled.csv', index=False)
    info = {'path': str((DATA/'ec2_cpu_utilization.csv').relative_to(ROOT)), 'rows': len(frame),
            'sha256': sha(raw), 'source_url': f'{base}/data/{KEY}', 'source_commit': commit,
            'labels_url': f'{base}/labels/combined_labels.json', 'labels_sha256': sha(label_bytes),
            'labeled_sha256': sha((DATA/'nab_cpu_labeled.csv').read_bytes()),
            'anomaly_labels': labels, 'anomaly_count': len(labels),
            'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
            'first_timestamp': str(frame['timestamp'].iloc[0]), 'last_timestamp': str(frame['timestamp'].iloc[-1]),
            'note': 'AWS EC2 CPU metric; no evidence of DBMS workload. Values kept in source scale; no inferred unit conversion. Pointwise labels, not official NAB window scoring.'}
    write_json(provenance_path, info)
    return info

def save_charts(run):
    names = run.metadata['model_names']
    pred = run.predictions
    fig, axes = plt.subplots(4, 1, figsize=(13, 10), sharex=True)
    for ax, name in zip(axes, names):
        ax.plot(run.frame['timestamp'], run.frame['value'], color='#a6b3c9', lw=.7)
        ax.axvline(pred['timestamp'].iloc[0], color='#304f77', ls='--', label='Test start')
        flags = pred[pred[f'{name}_prediction'] == -1]
        truth = pred[pred['is_anomaly'] == -1]
        ax.scatter(flags['timestamp'], flags['value'], s=11, c='#db6743', label='Predicted anomaly', zorder=3)
        ax.scatter(truth['timestamp'], truth['value'], s=65, marker='x', c='#151d36', label='NAB point label', zorder=4)
        ax.set_title(name, loc='left', fontsize=11)
        ax.set_ylabel('Source value')
        ax.grid(alpha=.2)
    axes[0].legend(loc='upper left', fontsize=8, ncol=3)
    fig.suptitle('NAB CPU | same chronological split, value feature, fixed parameters', fontsize=13)
    fig.tight_layout()
    fig.savefig(RESULTS/'nab_predictions.png', dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(names))
    for i, key in enumerate(('precision', 'recall', 'f1')):
        heights = [run.metrics[name][key] for name in names]
        bars = ax.bar(x+(i-1)*.24, heights, .24, label=key)
        ax.bar_label(bars, fmt='%.3f', fontsize=8, padding=3)
    ax.set_xticks(x, names)
    ax.set_ylim(0, 1.16)
    ax.set_ylabel('Pointwise metric')
    ax.set_title('Sparse exact-point labels | not official NAB scoring')
    ax.legend(ncol=3, loc='upper right')
    ax.grid(axis='y', alpha=.15)
    fig.tight_layout()
    fig.savefig(RESULTS/'comparison.png', dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.8))
    for ax, name in zip(axes, names):
        cm = confusion_matrix(pred['is_anomaly'], pred[f'{name}_prediction'], labels=[1,-1])
        ConfusionMatrixDisplay(cm, display_labels=['Normal', 'Anomaly']).plot(ax=ax, colorbar=False, cmap='Blues')
        ax.set_title(name, fontsize=10)
    fig.suptitle('Confusion matrices on the identical test rows')
    fig.tight_layout()
    fig.savefig(RESULTS/'confusion_matrices.png', dpi=160)
    plt.close(fig)

def execute_notebook():
    path = PROJECT/'notebooks'/'exploratory.ipynb'
    notebook = json.loads(path.read_text(encoding='utf-8-sig'))
    import contextlib
    namespace = {'__name__': '__main__'}
    outputs = []
    for index, cell in enumerate(notebook['cells']):
        if cell['cell_type'] == 'code':
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                exec(compile(''.join(cell['source']), f'{path.name}:cell{index}', 'exec'), namespace)
            outputs.append({'cell': index, 'stdout': stream.getvalue(), 'status': 'PASS'})
    write_json(RESULTS/'notebook_execution.json', {'method':'Execute all code cells sequentially in a fresh namespace; not a Jupyter browser run.', 'cells':outputs})

def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    info = prepare_data()
    run = run_detection(DATA/'nab_cpu_labeled.csv', label_col='is_anomaly')
    local = run_detection(DATA/'cpu_0.csv')
    for name, item in [('nab',run),('local_sample',local)]:
        (RESULTS/f'{name}_predictions.csv').write_bytes(item.export_csv())
        write_json(RESULTS/f'{name}_run.json', item.summary())
    pd.DataFrame(run.metrics).T.to_csv(RESULTS/'metrics.csv', index_label='model')
    save_charts(run)
    packages = ['numpy','pandas','scikit-learn','scipy','matplotlib','fastapi','uvicorn','streamlit','plotly','python-docx','python-pptx','httpx','python-multipart']
    environment = {'python':sys.version, 'packages':{p:importlib.metadata.version(p) for p in packages}}
    write_json(RESULTS/'environment.json', environment)
    summary = {'dataset': info, 'config': {'train_fraction':.7, 'contamination':.01, 'random_state':42,
               'features':['value'], 'label_policy':'Exact NAB combined_labels point timestamps; positive anomaly=-1. No official NAB window scoring; no parameter tuning on test.'},
               'runs': {'nab': {'metadata':run.metadata, 'metrics':run.metrics},
                        'local_sample': {'metadata':local.metadata, 'metrics':local.metrics}},
               'verification': {'notebook':'pending', 'tests':'pending', 'http':'pending', 'ui':'pending'}}
    write_json(RESULTS/'summary.json', summary)
    execute_notebook()
    summary['verification']['notebook'] = 'PASS: all notebook code cells executed; see notebook_execution.json'
    write_json(RESULTS/'summary.json', summary)
    print(json.dumps({'rows':info['rows'], 'train':run.metadata['train_rows'], 'test':run.metadata['test_rows'], 'metrics':run.metrics}, indent=2))

if __name__ == '__main__':
    main()