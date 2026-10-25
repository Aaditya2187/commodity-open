"""Online learners shared by the research replay and ``model.py``.

``fit`` sees only rows whose outcome was known before ``train_end``. ``update`` sees only the
learning copy's own matured outcomes. ``y`` is +1 (up barrier first), -1 (down first), or 0
(neither or ambiguous); rows with ``y == 0`` are not learned from. ``proba`` is P(up first).

Features: ``gap_thr``, ``f_ret_5``, ``f_ret_20``, ``f_hl_night_pos``, ``f_dist_ma_20``, ``h``,
an asset one-hot, and optionally ``news_night``, ``news_day``, and ``path_0`` .. ``path_11``
(last 12 hourly log returns, most recent first, in thresholds).
"""
from __future__ import annotations

import copy
import gc
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

SEED = 20261025
ASSETS = ("gold", "silver", "copper", "crude")
BASE_FEATS = ("gap_thr", "f_ret_5", "f_ret_20", "f_hl_night_pos", "f_dist_ma_20", "h")
NEWS_FEATS = ("news_night", "news_day")
PATH_FEATS = tuple(f"path_{i}" for i in range(12))
CAT_PARAMS = dict(
    iterations=200,
    depth=3,
    learning_rate=0.05,
    l2_leaf_reg=5,
    random_seed=SEED,
    verbose=False,
    thread_count=1,
    allow_writing_files=False,
    used_ram_limit="1gb",
)


def _feats_from_params(params: dict) -> tuple[str, ...]:
    if params.get("feats"):
        return tuple(params["feats"])
    feats = list(BASE_FEATS)
    if params.get("news"):
        feats.extend(NEWS_FEATS)
    if params.get("kind") == "gru" or params.get("path"):
        feats.extend(PATH_FEATS)
    return tuple(feats)


def as_frame(row) -> pd.DataFrame:
    if isinstance(row, pd.DataFrame):
        return row
    if isinstance(row, pd.Series):
        return row.to_frame().T
    if hasattr(row, "_asdict"):
        return pd.DataFrame([row._asdict()])
    if isinstance(row, dict):
        return pd.DataFrame([row])
    raise TypeError(type(row).__name__)


def matrix(frame: pd.DataFrame, feats: tuple[str, ...]) -> np.ndarray:
    d = frame.reindex(columns=list(feats)).apply(pd.to_numeric, errors="coerce").fillna(0.0)
    X = d.to_numpy(dtype=np.float64)
    asset = frame["asset"].astype(str).to_numpy() if "asset" in frame.columns else np.array(["gold"] * len(frame))
    A = np.stack([(asset == a).astype(np.float64) for a in ASSETS], axis=1)
    return np.hstack([X, A])


def _gap_sign(row) -> int:
    frame = as_frame(row)
    if "gap_thr" not in frame.columns or not len(frame):
        return 1
    g = float(pd.to_numeric(frame["gap_thr"].iloc[0], errors="coerce") or 0.0)
    if not np.isfinite(g) or g == 0:
        return 1
    return 1 if g > 0 else -1


def _new_catboost():
    from catboost import CatBoostClassifier

    return CatBoostClassifier(**CAT_PARAMS)


def _fit_cat(X: np.ndarray, y: np.ndarray, sample_weight: np.ndarray | None):
    if len(y) < 20 or y.min() == y.max():
        return None
    model = _new_catboost()
    model.fit(X, y, sample_weight=sample_weight)
    return model


def _cat_proba(model, X: np.ndarray) -> np.ndarray:
    if model is None:
        return np.full(len(X), 0.5)
    return model.predict_proba(X)[:, 1]


@dataclass
class RefitCat:
    """CatBoost refit every ``every`` sessions on the training rows plus delivered outcomes."""

    every: int = 5
    feats: tuple[str, ...] = BASE_FEATS
    recent_w: float = 2.0
    seed: int = SEED
    train: pd.DataFrame | None = None
    buf: list = field(default_factory=list)
    last_refit: int = -10**9
    model: object = None

    def fit(self, train: pd.DataFrame) -> None:
        self.train = train.reset_index(drop=True)
        self.buf = []
        self.last_refit = -10**9
        self.model = self._fit(self.train, None)
        gc.collect()

    def _fit(self, frame: pd.DataFrame, recent_mask: np.ndarray | None):
        d = frame.reset_index(drop=True)
        y_raw = pd.to_numeric(d["y"], errors="coerce").fillna(0).to_numpy()
        keep = y_raw != 0
        if recent_mask is not None:
            recent_mask = np.asarray(recent_mask)[: len(d)]
        d = d.loc[keep]
        y = (y_raw[keep] == 1).astype(int)
        weight = None
        if recent_mask is not None:
            weight = np.where(recent_mask[keep], self.recent_w, 1.0).astype(np.float64)
        return _fit_cat(matrix(d, self.feats), y, weight)

    def proba(self, row) -> float:
        frame = as_frame(row)
        if self.model is None:
            return 1.0 if _gap_sign(frame) > 0 else 0.0
        return float(_cat_proba(self.model, matrix(frame, self.feats))[0])

    def predict(self, row) -> int:
        return 1 if self.proba(row) >= 0.5 else -1

    def update(self, rows: pd.DataFrame, step: int) -> None:
        if rows is None or len(rows) == 0:
            return
        self.buf.append(rows.reset_index(drop=True))
        if int(step) - self.last_refit >= self.every:
            parts = [self.train] + self.buf
            d = pd.concat(parts, ignore_index=True)
            mask = np.zeros(len(d), dtype=bool)
            mask[len(self.train) :] = True
            self.model = self._fit(d, mask)
            self.last_refit = int(step)
            gc.collect()

    def __deepcopy__(self, memo):
        twin = RefitCat(every=self.every, feats=self.feats, recent_w=self.recent_w, seed=self.seed)
        twin.train = None if self.train is None else self.train.copy()
        twin.buf = [b.copy() for b in self.buf]
        twin.last_refit = self.last_refit
        twin.model = None if self.model is None else self.model.copy()
        memo[id(self)] = twin
        return twin


class NeuralOnline:
    """Seed-averaged MLP, or a GRU over the 12-hour path plus the static features.

    ``fit`` warm-starts, then runs the same online step through pre-cutoff slots in date order.
    ``update`` takes ``k`` steps of a fresh Adam on the delivered rows mixed with a sample of the
    original training rows.
    """

    def __init__(
        self,
        kind: str = "mlp",
        k: int = 3,
        lr: float = 3e-4,
        feats: tuple[str, ...] = BASE_FEATS,
        seeds: int = 5,
        hidden: int = 16,
        epochs: int = 8,
        sample: int = 64,
    ) -> None:
        self.kind = kind
        self.k = int(k)
        self.lr = float(lr)
        if kind == "gru":
            rest = [f for f in feats if not str(f).startswith("path_")]
            self.feats = tuple(PATH_FEATS) + tuple(rest)
        else:
            self.feats = tuple(feats)
        self.n_seeds = int(seeds)
        self.hidden = int(hidden)
        self.epochs = int(epochs)
        self.sample = int(sample)
        self.seeds = [SEED + i * 17 for i in range(self.n_seeds)]
        self.models: list = []
        self.pool: pd.DataFrame | None = None
        self.mu: np.ndarray | None = None
        self.sd: np.ndarray | None = None
        self.ready = False
        self._torch = None

    def _th(self):
        if self._torch is None:
            import torch

            torch.set_num_threads(1)
            try:
                torch.set_num_interop_threads(1)
            except RuntimeError:
                pass
            self._torch = torch
        return self._torch

    def _X(self, frame: pd.DataFrame) -> np.ndarray:
        return matrix(frame, self.feats).astype(np.float32)

    def _standardize(self, X: np.ndarray, fit: bool) -> np.ndarray:
        if fit:
            self.mu = X.mean(axis=0).astype(np.float32)
            self.sd = X.std(axis=0).astype(np.float32)
            self.sd[self.sd < 1e-6] = 1.0
        return (X - self.mu) / self.sd

    def _build(self, d_in: int):
        torch = self._th()

        class MLP(torch.nn.Module):
            def __init__(self, d, h):
                super().__init__()
                self.net = torch.nn.Sequential(torch.nn.Linear(d, h), torch.nn.ReLU(), torch.nn.Linear(h, 1))

            def forward(self, x):
                return self.net(x).reshape(-1)

        class GRUNet(torch.nn.Module):
            def __init__(self, n_path, n_static, h):
                super().__init__()
                self.n_path = n_path
                self.gru = torch.nn.GRU(input_size=1, hidden_size=h, batch_first=True)
                self.head = torch.nn.Linear(h + n_static, 1)

            def forward(self, x):
                path = x[:, : self.n_path].flip(1).unsqueeze(-1)  # chronological; path_0 was most recent
                static = x[:, self.n_path :]
                out, _ = self.gru(path)
                return self.head(torch.cat([out[:, -1, :], static], dim=1)).reshape(-1)

        models = []
        n_path = sum(1 for f in self.feats if str(f).startswith("path_"))
        for seed in self.seeds:
            torch.manual_seed(seed)
            if self.kind == "gru":
                n_static = d_in - n_path
                models.append(GRUNet(n_path, n_static, self.hidden))
            else:
                models.append(MLP(d_in, self.hidden))
        self.models = models

    def _logits(self, model, X: np.ndarray):
        torch = self._th()
        return model(torch.from_numpy(np.ascontiguousarray(X))).reshape(-1)

    def _warmup(self, X: np.ndarray, y: np.ndarray) -> None:
        torch = self._th()
        loss_fn = torch.nn.BCEWithLogitsLoss()
        yt = torch.from_numpy(y.astype(np.float32))
        n = len(y)
        for seed, model in zip(self.seeds, self.models):
            opt = torch.optim.Adam(model.parameters(), lr=self.lr, betas=(0.8, 0.95))
            model.train()
            for ep in range(self.epochs):
                perm = np.random.default_rng(seed + ep).permutation(n)
                for i in range(0, n, 256):
                    idx = perm[i : i + 256]
                    if len(idx) == 0:
                        continue
                    opt.zero_grad()
                    logit = self._logits(model, X[idx])
                    loss_fn(logit, yt[idx]).backward()
                    opt.step()

    def _steps(self, X: np.ndarray, y: np.ndarray) -> None:
        if len(y) == 0 or not self.models:
            return
        torch = self._th()
        loss_fn = torch.nn.BCEWithLogitsLoss()
        yt = torch.from_numpy(y.astype(np.float32))
        for model in self.models:
            opt = torch.optim.Adam(model.parameters(), lr=self.lr, betas=(0.8, 0.95))
            model.train()
            for _ in range(self.k):
                opt.zero_grad()
                logit = self._logits(model, X)
                loss_fn(logit, yt).backward()
                opt.step()

    def _xy(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        d = frame.reset_index(drop=True)
        y_raw = pd.to_numeric(d["y"], errors="coerce").fillna(0).to_numpy()
        keep = y_raw != 0
        d = d.loc[keep]
        X = self._standardize(self._X(d), fit=False)
        y = (y_raw[keep] == 1).astype(np.float32)
        return X, y

    def fit(self, train: pd.DataFrame) -> None:
        d = train.reset_index(drop=True)
        y_raw = pd.to_numeric(d["y"], errors="coerce").fillna(0).to_numpy()
        decided = d.loc[y_raw != 0].reset_index(drop=True)
        self.pool = decided
        self.ready = False
        self.models = []
        if len(decided) < 20 or decided["y"].nunique() < 2:
            return
        X0 = self._X(decided)
        X = self._standardize(X0, fit=True)
        y = (pd.to_numeric(decided["y"], errors="coerce").to_numpy() == 1).astype(np.float32)
        self._build(X.shape[1])
        self._warmup(X, y)
        self.ready = True
        if "gidx" in decided.columns:
            for g, grp in decided.groupby("gidx", sort=True):
                self.update(grp, int(g))
        gc.collect()

    def proba(self, row) -> float:
        if not self.ready:
            return 1.0 if _gap_sign(row) > 0 else 0.0
        torch = self._th()
        X = self._standardize(self._X(as_frame(row)), fit=False)
        ps = []
        for model in self.models:
            model.eval()
            with torch.no_grad():
                ps.append(torch.sigmoid(self._logits(model, X)).numpy())
        return float(np.mean(ps))

    def predict(self, row) -> int:
        return 1 if self.proba(row) >= 0.5 else -1

    def update(self, rows: pd.DataFrame, step: int) -> None:
        if not self.ready or rows is None or len(rows) == 0 or self.pool is None or len(self.pool) == 0:
            return
        delivered = rows.reset_index(drop=True)
        y_raw = pd.to_numeric(delivered["y"], errors="coerce").fillna(0).to_numpy()
        delivered = delivered.loc[y_raw != 0]
        if len(delivered) == 0:
            return
        rng = np.random.default_rng(SEED + int(step) + 3)
        n = min(self.sample, len(self.pool))
        take = rng.choice(len(self.pool), size=n, replace=False)
        mixed = pd.concat([delivered, self.pool.iloc[take]], ignore_index=True)
        X, y = self._xy(mixed)
        self._steps(X, y)

    def __deepcopy__(self, memo):
        torch = self._th()
        twin = NeuralOnline(
            kind=self.kind,
            k=self.k,
            lr=self.lr,
            feats=self.feats,
            seeds=self.n_seeds,
            hidden=self.hidden,
            epochs=self.epochs,
            sample=self.sample,
        )
        twin.seeds = list(self.seeds)
        twin.pool = None if self.pool is None else self.pool.copy()
        twin.mu = None if self.mu is None else self.mu.copy()
        twin.sd = None if self.sd is None else self.sd.copy()
        twin.ready = self.ready
        twin.models = [copy.deepcopy(m) for m in self.models]
        for m in twin.models:
            m.load_state_dict(m.state_dict())
        memo[id(self)] = twin
        # touch torch so the copied modules stay tied to this interpreter
        _ = torch
        return twin


@dataclass
class AppendEnsemble:
    """Every ``every`` sessions, append a new CatBoost. Keep at most 8, always the original fit.

    Weight = ``alpha`` * accuracy on the last 40 outcomes + ``(1 - alpha)`` * recency.
    """

    every: int = 5
    alpha: float = 0.5
    feats: tuple[str, ...] = BASE_FEATS
    members: list = field(default_factory=list)
    known: pd.DataFrame | None = None
    history: list = field(default_factory=list)
    last: int = -10**9
    window: int = 40
    cap: int = 8

    def fit(self, train: pd.DataFrame) -> None:
        self.known = train.reset_index(drop=True)
        self.history = []
        self.last = -10**9
        self.members = []
        model = self._fit_frame(self.known)
        if model is not None:
            self.members.append(model)
        gc.collect()

    def _fit_frame(self, frame: pd.DataFrame):
        d = frame.reset_index(drop=True)
        y_raw = pd.to_numeric(d["y"], errors="coerce").fillna(0).to_numpy()
        d = d.loc[y_raw != 0]
        y = (y_raw[y_raw != 0] == 1).astype(int)
        return _fit_cat(matrix(d, self.feats), y, None)

    def _weights(self) -> np.ndarray:
        n = len(self.members)
        if n == 0:
            return np.zeros(0)
        if not self.history:
            return np.ones(n) / n
        hist = pd.DataFrame(self.history)
        y = pd.to_numeric(hist["y"], errors="coerce").fillna(0).to_numpy()
        X = matrix(hist, self.feats)
        acc = []
        for model in self.members:
            pred = np.where(_cat_proba(model, X) >= 0.5, 1, -1)
            acc.append(float((pred == y).mean()) if len(y) else 0.5)
        acc = np.asarray(acc, dtype=np.float64)
        recency = np.linspace(0.0, 1.0, n) if n > 1 else np.ones(1)
        w = self.alpha * acc + (1.0 - self.alpha) * recency
        if float(w.sum()) <= 0:
            return np.ones(n) / n
        return w / w.sum()

    def proba(self, row) -> float:
        if not self.members:
            return 1.0 if _gap_sign(row) > 0 else 0.0
        X = matrix(as_frame(row), self.feats)
        ps = np.array([float(_cat_proba(m, X)[0]) for m in self.members])
        return float(np.dot(self._weights(), ps))

    def predict(self, row) -> int:
        return 1 if self.proba(row) >= 0.5 else -1

    def update(self, rows: pd.DataFrame, step: int) -> None:
        if rows is None or len(rows) == 0:
            return
        d = rows.reset_index(drop=True)
        y_raw = pd.to_numeric(d["y"], errors="coerce").fillna(0).to_numpy()
        decided = d.loc[y_raw != 0]
        if len(decided):
            self.known = pd.concat([self.known, decided], ignore_index=True)
            self.history.extend(decided.to_dict("records"))
            self.history = self.history[-self.window :]
        if int(step) - self.last >= self.every:
            model = self._fit_frame(self.known)
            self.last = int(step)
            if model is None:
                return
            self.members.append(model)
            while len(self.members) > self.cap:
                # drop the oldest member that is not the original fit
                del self.members[1]
            gc.collect()

    def __deepcopy__(self, memo):
        twin = AppendEnsemble(every=self.every, alpha=self.alpha, feats=self.feats)
        twin.members = [m.copy() for m in self.members]
        twin.known = None if self.known is None else self.known.copy()
        twin.history = [dict(h) for h in self.history]
        twin.last = self.last
        memo[id(self)] = twin
        return twin


@dataclass
class Blend:
    """Fixed-weight average of a RefitCat and a NeuralOnline."""

    w_refit: float = 0.5
    every: int = 5
    k: int = 3
    lr: float = 3e-4
    feats: tuple[str, ...] = BASE_FEATS
    refit: RefitCat | None = None
    neural: NeuralOnline | None = None

    def __post_init__(self) -> None:
        self.refit = RefitCat(every=self.every, feats=self.feats)
        self.neural = NeuralOnline(kind="mlp", k=self.k, lr=self.lr, feats=self.feats)

    def fit(self, train: pd.DataFrame) -> None:
        self.refit.fit(train)
        self.neural.fit(train)

    def proba(self, row) -> float:
        return float(self.w_refit) * self.refit.proba(row) + (1.0 - float(self.w_refit)) * self.neural.proba(row)

    def predict(self, row) -> int:
        return 1 if self.proba(row) >= 0.5 else -1

    def update(self, rows: pd.DataFrame, step: int) -> None:
        self.refit.update(rows, step)
        self.neural.update(rows, step)


def make(name: str, **params):
    """Build one of ``refit``, ``neural``, ``append``, ``blend``."""
    kind = str(name).lower()
    feats = _feats_from_params(params)
    if kind == "refit":
        return RefitCat(every=int(params.get("every", 5)), feats=feats, recent_w=float(params.get("recent_w", 2.0)))
    if kind == "neural":
        return NeuralOnline(
            kind=str(params.get("kind", "mlp")),
            k=int(params.get("k", 3)),
            lr=float(params.get("lr", 3e-4)),
            feats=feats,
            seeds=int(params.get("seeds", 5)),
            hidden=int(params.get("hidden", 16)),
        )
    if kind == "append":
        return AppendEnsemble(every=int(params.get("every", 5)), alpha=float(params.get("alpha", 0.5)), feats=feats)
    if kind == "blend":
        return Blend(
            w_refit=float(params.get("w_refit", 0.5)),
            every=int(params.get("every", 5)),
            k=int(params.get("k", 3)),
            lr=float(params.get("lr", 3e-4)),
            feats=feats,
        )
    raise ValueError(name)
