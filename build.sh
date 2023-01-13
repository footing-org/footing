poetry build
rm -f *.whl
mv dist/footing*.whl .
rm -rf dist