#!/bin/sh

###
# Build distribution
###

rm -rf dist
poetry build
cp dist/*.whl install/