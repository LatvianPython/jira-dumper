.PHONY: all init build

all: init build

init:
    pip install -r requirements.txt

build:
    setup.py install
