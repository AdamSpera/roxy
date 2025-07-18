"""
Setup script for Roxy package.
"""

from setuptools import setup, find_packages

setup(
    name="roxy",
    version="0.1.0",
    description="Lightweight proxy tool for HTTP/S, SSH, & Telnet",
    author="Adam Spera",
    author_email="adamspera@hotmail.com",
    url="https://github.com/adamspera/roxy",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "roxy": [
            "static/**/*",
            "static/ciscoish/**/*",
            "static/ciscoish/SharpSans-Bold/**/*",
            "static/ciscoish/inter/**/*",
            "static/ciscoish/roboto-mono/**/*",
            "templates/**/*",
        ],
    },
    install_requires=[
        "flask",
        "gunicorn",
        "click",
        "tabulate",
    ],
    entry_points={
        "console_scripts": [
            "roxy=roxy.cli:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Internet :: Proxy Servers",
    ],
    python_requires=">=3.6",
)