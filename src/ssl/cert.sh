#!/bin/bash

# Keychain_Name=$(security list-keychains | grep $(whoami) | tr -d '"')

TRUSTED=`security dump-trust-settings -d | grep ecslocal`

FORCE_UPDATE=$1

if [ -z "$TRUSTED" ] || [ $FORCE_UPDATE ]; then
    echo 'Deleting ecslocal trusted certificates'
    sudo security delete-certificate -c 'ecslocal' /Library/Keychains/System.keychain
    # sudo security delete-certificate -c 'localhost' ~/Library/Keychains/login.keychain-db
    echo ''

    # ~/Library/Keychains/login.keychain-db
    sudo security add-trusted-cert -p ssl -p smime -p codeSign -p IPSec -p eap -p basic -p swUpdate -p pkgSign -p timestamping -d -r trustRoot -k /Library/Keychains/System.keychain volumes/certificates/rootCA.crt
    # sudo security add-trusted-cert -p ssl -p smime -p codeSign -p IPSec -p eap -p basic -p swUpdate -p pkgSign -p timestamping -d -r trustAsRoot -k /Library/Keychains/System.keychain volumes/certificates/cert.pem
fi
