import numpy as np


def brier_1x2(predictions, outcomes):
    """predictions: Nx3 [H,D,A], outcomes: 0/1/2"""
    p = np.asarray(predictions, dtype=float)
    y = np.eye(3)[np.asarray(outcomes, dtype=int)]
    return float(np.mean(np.sum((p-y)**2, axis=1)))


def log_loss_1x2(predictions, outcomes, eps=1e-15):
    p = np.asarray(predictions, dtype=float)
    p = np.clip(p, eps, 1-eps)
    return float(-np.mean(np.log(p[np.arange(len(outcomes)), np.asarray(outcomes, dtype=int)])))
