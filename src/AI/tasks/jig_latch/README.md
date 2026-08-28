# Jig-latch-segement - Hailo-H8 Compilation Project

## Folder Structure

```
Jig-latch-segement/
├── calibration_data/    # Calibration images for quantization (100-1000 images recommended)
├── models/
│   ├── onnx/            # Original ONNX model files
│   ├── har/             # Hailo Archive files (intermediate compilation output)
│   └── hef/             # Hailo Executable Format (final compiled model)
├── configs/             # Hailo model configuration files (.alls, .yaml)
├── scripts/             # Compilation and inference scripts
├── test/
│   ├── images/          # Test images for inference
│   ├── videos/          # Test videos for inference
│   └── results/         # Inference output results
└── logs/                # Compilation and inference logs
```

## Data Preparation Checklist

1. **calibration_data/**: Add 100-1000 representative images (same format as training data)
2. **models/onnx/**: Place your exported ONNX model here
3. **test/images/**: Add test images for validation

## Hailo Compilation Workflow

1. Parse ONNX -> HAR
2. Optimize HAR with calibration data
3. Compile HAR -> HEF
4. Test HEF on device
