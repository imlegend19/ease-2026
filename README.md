# EASE 2026 Experiment Workspace

This experiment uses the shared SmartSHARK MongoDB service in
`datasets/smartshark`. Mongo access in Python is through `pymongo`.

## 1. Start shared SmartSHARK MongoDB

From workspace root:

```powershell
cd datasets/smartshark
docker compose up -d mongo
docker compose --profile restore run --rm mongo-restore
```

## 2. Configure this experiment

From `experiments/ease-2026`:

```powershell
Copy-Item .env.example .env
```

Defaults:

- `SMARTSHARK_MONGO_URI=mongodb://smartshark:smartshark@localhost:27117/?authSource=admin`
- `SMARTSHARK_MONGO_DB=smartshark`

## 3. Create local `uv` environment (Python 3.12)

From `experiments/ease-2026`:

```powershell
# Install uv (one-time) if needed
irm https://astral.sh/uv/install.ps1 | iex

# Create local virtual environment with Python 3.12
uv venv --python 3.12 .venv
```

## 4. Install experiment dependencies (latest)

From `experiments/ease-2026`:

```powershell
uv pip install --python .venv\Scripts\python.exe --upgrade `
  pandas numpy scipy matplotlib seaborn pymongo rbo rpy2 `
  networkx upsetplot scikit-learn
```

## 5. Verify the environment

```powershell
.venv\Scripts\python.exe --version
uv pip list --python .venv\Scripts\python.exe
```

## Notes

- Dependency set above was derived from `experiments/saner-2026` scripts and requirements.
- `experiments/saner-2026/rq3_scott-knot.py` imports `from sk import Rx`; this helper module is not present in `saner-2026` as a pip dependency.
