from setuptools import setup, find_packages

setup(
    name="z3ro-assistant",
    version="1.0.0",
    packages=find_packages(),
    py_modules=["name"],
    entry_points={
        "console_scripts": [
            "name = name:main",
            "z3ro = name:main",
            "sobia = name:main",
        ],
    },
)
