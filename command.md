Step 1 — Run the benchmark (1 trial, 20 tasks, DeepSeek agent):


cd /home/nurye/Desktop/TRP1/week10/TheConversionEngine
bash eval/run_tau2_retail.sh
Step 2 — Compute rewards on the output (run immediately after Step 1 finishes):

The run creates a timestamped folder. Evaluate it like this:
SIM_DIR=$(ls -dt eval/tau2-bench/data/simulations/*/  | head -1)
cd eval/tau2-bench
uv run tau2 evaluate-trajs "$SIM_DIR"