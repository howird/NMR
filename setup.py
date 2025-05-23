from setuptools import setup, find_packages
import unittest

from torch.utils.cpp_extension import BuildExtension, CUDAExtension

CUDA_FLAGS = []


def test_all():
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover("tests", pattern="test_*.py")
    return test_suite


ext_modules = [
    CUDAExtension(
        "neural_renderer.cuda.load_textures",
        [
            "neural_renderer/cuda/load_textures_cuda.cpp",
            "neural_renderer/cuda/load_textures_cuda_kernel.cu",
        ],
    ),
    CUDAExtension(
        "neural_renderer.cuda.rasterize",
        [
            "neural_renderer/cuda/rasterize_cuda.cpp",
            "neural_renderer/cuda/rasterize_cuda_kernel.cu",
        ],
    ),
    CUDAExtension(
        "neural_renderer.cuda.create_texture_image",
        [
            "neural_renderer/cuda/create_texture_image_cuda.cpp",
            "neural_renderer/cuda/create_texture_image_cuda_kernel.cu",
        ],
    ),
]

setup(
    name="neural_renderer_pytorch",
    test_suite="setup.test_all",
    packages=["neural_renderer", "neural_renderer.cuda"],
    ext_modules=ext_modules,
    cmdclass={"build_ext": BuildExtension},
)
