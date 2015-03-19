#!/bin/bash

if [ -f /home/vagrant/.mongodb_password_set ]; then
    exit 0
fi

sudo service mongodb start

PASS="password"

RET=1
while [[ RET -ne 0 ]]; do
    echo "=> Waiting for confirmation of MongoDB service startup"
    sleep 5
    mongo admin --eval "help" >/dev/null 2>&1
    RET=$?
done

echo "Creating mongodb users..."
mongo admin --eval "db.createUser({user: 'admin', pwd: 'password', roles: ['root']})"
mongo trunk --eval "db.createUser({user: 'user', pwd: 'password', roles: ['readWrite']});"
echo "Done!"
touch /home/vagrant/.mongodb_password_set
