import setuptools

from jira_dump import __version__

with open("README.rst", mode="r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="jira_dump",
    version=__version__,
    author="LatvianPython",
    author_email="kalvans.rolands@gmail.com",
    description="Tool to dump data from Jira",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://github.com/LatvianPython/jira-dumper",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Development Status :: 2 - Pre-Alpha",
    ],
    python_requires=">=3.8",
)
