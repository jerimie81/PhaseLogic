from setuptools import setup, find_packages

setup(
    name="smooth-bee",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["jinja2>=3.1"],
    entry_points={
        "console_scripts": [
            "smooth-bee=smooth_bee.cli:main",
        ]
    },
    python_requires=">=3.11",
)
