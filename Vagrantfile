# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/trusty64"
  config.vm.network "forwarded_port", guest: 80, host: 8080

  config.vm.provision "shell", inline: <<-SHELL
    sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
    echo "deb http://repo.mongodb.org/apt/ubuntu "$(lsb_release -sc)"/mongodb-org/3.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.0.list
    sudo apt-get update
    sudo apt-get install -y mongodb-org libzmq3-dev libssl-dev libcrypto++-dev build-essential python-dev python3-dev libpcre3-dev python-pip
    cd /vagrant
    python2 setup.py develop
    cp examples/forest.json /home/vagrant/.forest.json
    sh /vagrant/tools/set_mongodb_password.sh
    su vagrant -c "forest prepare"
    mkdir -p /etc/nginx
    cp /vagrant/examples/nginx.conf /etc/nginx/nginx.conf
    sudo apt-get install -o Dpkg::Options::="--force-confold" --force-yes nginx -y
  SHELL
end
