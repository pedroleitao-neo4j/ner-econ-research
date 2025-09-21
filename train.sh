#!/bin/sh
#
# Assumes you have created the conda environment `econ-ie` with:
#
# conda env create -f environment.yml
#
# And activated it with:
#
# conda activate econ-ie
#
# Pick a batch size that fits your GPU memory, an NVidia RTX 3900 with 24GB of RAM will fit a --batch_size 32
#
python tools/trainer.py --model_name worldbank/econberta-fs --train_file data/econ_ie/train.conll --validation_file data/econ_ie/dev.conll --test_file data/econ_ie/test.conll --output_dir models/econberta-fs-econ-ie-ner-tuned --epochs 5 --batch 32
