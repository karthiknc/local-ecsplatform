# Local ECS Platform
This repository helps you setup ECS platform and sites in your local machine.

## Setup
 - Install docker
 - Clone required site repositories to your local machine.
   - Eg: `~/projects/nu-tls-wp-cms`
 - Clone this repository to your local machine.
   - Eg: `~/projects/local-ecsplatform`
 - Copy `local_config_sample.py` to `local_config.py`
 - Add correct configuration to `local_config.py`

## Build
`./build true true true`
### Parameters
 - First parameter: Bool - Whether to build ECS Platform Image
 - Second parameter: Bool - Whether to build WP Platform Image
 - Third parameter: Bool - Whether to build site Image

## Run
`docker-compose up -d`

## ssh
`./ssh container_name`

## Stop containers
`docker-compose stop`

## Remove containers
`docker-compose down`
