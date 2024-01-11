# setup.py

from setuptools import setup, find_packages

setup(
    name="lexios",
    version="0.1",
    author="Hernán Alejandro García",
    description="Library to run a full server for Lexi, Api Assistant.",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "alembic",
        # Add other dependencies as needed
    ],
    entry_points={
        'console_scripts': [
            'lexios-admin=admin.main:__main__',
        ],
    },
)
