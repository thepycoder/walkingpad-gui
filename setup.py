#!/usr/bin/env python3
"""
Setup script for WalkingPad GUI Controller
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="walkingpad-gui",
    version="1.0.0",
    author="WalkingPad GUI Project",
    author_email="",
    description="A simple, compact GUI for controlling WalkingPad treadmills with Home Assistant integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/walkingpad-gui",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Hardware",
        "Topic :: Home Automation",
        "Environment :: X11 Applications",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "walkingpad-gui=walkingpad_gui.gui:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
) 