# Diploma thesis on the topic: "Research on Methods for Improving the Robustness of OCR Models to Visual Distortions and Noise"

[English](./README.md) | [Русский](./README_RU.md)

This work addresses the task of fine-tuning an OCR model based on the **PP-OCRv3** architecture for text recognition in document images affected by various visual distortions and noise. The primary focus is on developing a complete software pipeline for data preparation, synthetic document generation, realistic scanning defect simulation, and training of the text recognition model.
The aim of the study is to test the hypothesis that the robustness of an OCR system to noise and distortions can be improved by fine-tuning the PP-OCRv3 model on a specialized dataset containing both real and synthetically generated documents.
In the course of this work, software tools were developed for automatic OCR dataset preparation, visual artifact generation, text region cropping, and annotation formatting for PaddleOCR. Model training was performed on the high-performance computing cluster "Charisma" using distributed training across four NVIDIA V100 GPUs.
As a result, a fine-tuned OCR model was obtained and compared with the baseline PP-OCRv3 version on several test datasets. The conducted analysis revealed the impact of synthetic noise and the characteristics of the training dataset on the final text recognition quality.

## Repository Content

- **auto_markup_test** This folder contains programs that count CER, WER, and NED
- **documents_generator** This folder contains the programs responsible for generating the synthetic dataset
- **generate_ppocr_valid_dataset** This folder contains programs that convert all datasets into a valid PP-OCR format for fine-tuning
- **harizma** Learning outcomes and statistics
- **noise_generator** Generating noisy images
- **ocr_datasets** The initial transformation is the specification of datasets and their annotations. The folder with the datasets should be placed here
- **omnidocbench_split** Selecting the best options from the OmniDocBench benchmark for testing the trained and baseline model
- **train_test_split** Separation into training and validation subsamples
- **training_graphs** Rendering graphs of results from the training log

## Dataset
You can download all the datasets used in the work using this link: https://disk.360.yandex.ru/d/AW_bC0YCeXJgqA
