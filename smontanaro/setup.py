"for packaging..."

from setuptools import setup

setup(
    name='smontanaro',
    packages=['smontanaro'],
    include_package_data=True,
    install_requires=[
        'flask',
    ],
)
