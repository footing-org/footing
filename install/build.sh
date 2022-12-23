#!/bin/sh

###
# Build distribution
###

rm -rf dist
poetry build
mv dist/*.whl install/footing.whl