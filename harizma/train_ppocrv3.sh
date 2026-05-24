#!/bin/bash
#SBATCH --job-name=ppocr_train
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --gres=gpu:v100:4
#SBATCH --cpus-per-task=32
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err

echo "==== JOB INFO ===="
hostname
date

nvidia-smi
echo "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"

# ----------------------------
# Modules
# ----------------------------

source deactivate

module load Python/Anaconda_v11.2021
module load nvidia_sdk/nvhpc/24.5
module load CUDA/12.4

# ----------------------------
# Conda
# ----------------------------

conda activate paddleocr-training

# ----------------------------
# NCCL / Paddle settings
# ----------------------------

export PYTHONNOUSERSITE=1

export NCCL_DEBUG=WARN

export NCCL_IB_DISABLE=1

export NCCL_IGNORE_CPU_AFFINITY=1

export FLAGS_allocator_strategy=auto_growth

export CUDA_DEVICE_MAX_CONNECTIONS=1

# ----------------------------
# Workdir
# ----------------------------

cd /home/ayuznakov/python/paddleocr_training/PaddleOCR

# ----------------------------
# Train
# ----------------------------

python -m paddle.distributed.launch \
  --gpus '0,1,2,3' \
  tools/train.py \
  -c configs/rec/my_rec.yml