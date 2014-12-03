#!/bin/bash
mkdir build && cd build
wget http://projects.unbit.it/downloads/uwsgi-2.0.8.tar.gz && tar -xzf uwsgi-2.0.8.tar.gz
cd uwsgi-2.0.8
cp ../../forest.ini buildconf
python2 uwsgiconfig.py --build forest
python2 uwsgiconfig.py --plugin plugins/python forest python2
python3 uwsgiconfig.py --plugin plugins/python forest python3
cp uwsgi python2_plugin.so python3_plugin.so ../../
cd ../..
rm build -r
