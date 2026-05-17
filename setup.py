from setuptools import setup, find_packages

setup(
    name="phaselogic",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "jinja2>=3.1",
        "requests>=2.31",
    ],
    extras_require={
        "dev": ["pytest>=8"],
    },
    entry_points={
        "console_scripts": [
            "phaselogic=phaselogic.cli:main",
        ]
    },
    python_requires=">=3.11",
)
