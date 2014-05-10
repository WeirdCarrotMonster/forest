#!/bin/bash
mkdir build && cd build
wget http://projects.unbit.it/downloads/uwsgi-2.0.4.tar.gz && tar -xzf uwsgi-2.0.4.tar.gz
cd uwsgi-2.0.4
python2 uwsgiconfig.py --build
printf "NAME='emperor_zeromq'\nCFLAGS = ['-lzmq']\nLDFLAGS = []\nLIBS = []\nGCC_LIST = ['emperor_zeromq']\n" > plugins/emperor_zeromq/uwsgiplugin.py
python2 uwsgiconfig.py --plugin plugins/emperor_zeromq
cp uwsgi emperor_zeromq_plugin.so ../../
cd ../..
rm build -r