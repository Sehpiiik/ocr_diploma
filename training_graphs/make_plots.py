import re
import argparse
import os
import numpy as np
import matplotlib.pyplot as plt

step_re = re.compile(r"global_step:\s*(\d+)")
epoch_re = re.compile(r"epoch:\s*\[(\d+)/(\d+)\]")

loss_re = re.compile(r"loss:\s*([\d.]+)")
acc_re = re.compile(r"acc:\s*([\d.]+)")
ned_re = re.compile(r"norm_edit_dis:\s*([\d.]+)")

eval_acc_re = re.compile(r"cur metric.*?acc:\s*([\d.]+)")
eval_ned_re = re.compile(r"cur metric.*?norm_edit_dis:\s*([\d.]+)")

def ema(values, beta=0.9):
    if len(values) == 0:
        return values
    out = []
    v = values[0]
    for x in values:
        v = beta * v + (1 - beta) * x
        out.append(v)
    return out
    
def plot(x, y, title, ylabel, out_path, best_idx=None):
    if len(x) == 0 or len(y) == 0:
        print(f"[WARN] Skipping {title}: empty data")
        return

    plt.figure(figsize=(10, 4))

    plt.plot(x, y, alpha=0.3, label="raw")
    plt.plot(x, ema(y), linewidth=2, label="EMA")

    # Best marker
    if best_idx is not None and 0 <= best_idx < len(x):
        plt.scatter([x[best_idx]], [y[best_idx]], color="red", label="best")

    plt.title(title)
    plt.xlabel("global_step")
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.legend()

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--log-file", type=str, required=True)
    parser.add_argument("--out-dir", type=str, default="plots")
    parser.add_argument("--ema-beta", type=float, default=0.9)

    args =parser.parse_args()
    
    os.makedirs(args.out_dir, exist_ok=True)

    train_steps, train_loss, train_acc, train_ned = [], [], [], []
    eval_steps, eval_acc, eval_ned = [], [], []

    last_step = 0

    with open(args.log_file, "r") as f:
        for line in f:

            m = step_re.search(line)
            if m:
                last_step = int(m.group(1))

            if "global_step" in line and "cur metric" not in line:
                m_loss = loss_re.search(line)
                m_acc = acc_re.search(line)
                m_ned = ned_re.search(line)

                if m_acc and m_ned:  # main signal
                    train_steps.append(last_step)
                    train_acc.append(float(m_acc.group(1)))
                    train_ned.append(float(m_ned.group(1)))

                    if m_loss:
                        train_loss.append(float(m_loss.group(1)))

            if "cur metric" in line:
                m_acc = eval_acc_re.search(line)
                m_ned = eval_ned_re.search(line)

                if m_acc and m_ned:
                    eval_steps.append(last_step)
                    eval_acc.append(float(m_acc.group(1)))
                    eval_ned.append(float(m_ned.group(1)))

    print(f"Train points: {len(train_steps)}")
    print(f"Eval points: {len(eval_steps)}")

    if len(train_steps) == 0:
        raise RuntimeError("No training data parsed. Check log format or regex.")

    best_train_acc_idx = int(np.argmax(train_acc))
    best_eval_acc_idx = int(np.argmax(eval_acc)) if eval_acc else None

    best_train_ned_idx = int(np.argmax(train_ned))
    best_eval_ned_idx = int(np.argmax(eval_ned)) if eval_ned else None

    best_train_loss_idx = int(np.argmin(train_loss)) if train_loss else None

    plot(
        train_steps, train_loss,
        "Train Loss",
        "loss",
        f"{args.out_dir}/train_loss.png",
        best_train_loss_idx
    )

    plot(
        train_steps, train_acc,
        "Train Accuracy",
        "acc",
        f"{args.out_dir}/train_acc.png",
        best_train_acc_idx
    )

    plot(
        train_steps, train_ned,
        "Train NED",
        "norm_edit_dis",
        f"{args.out_dir}/train_ned.png",
        best_train_ned_idx
    )

    if eval_acc:
        plot(
            eval_steps, eval_acc,
            "Eval Accuracy",
            "acc",
            f"{args.out_dir}/eval_acc.png",
            best_eval_acc_idx
        )

    if eval_ned:
        plot(
            eval_steps, eval_ned,
            "Eval NED",
            "norm_edit_dis",
            f"{args.out_dir}/eval_ned.png",
            best_eval_ned_idx
        )


if __name__ == "__main__":
    SystemExit(main())
