README
======
The aws-provisioning demo provides a means of provisioning and supporting instances in the AWS cloud using Boto, Fabric,
and Cloud Formation templates. This sample project supports launching a MongoDB Replica Set. Each instance runs Ubuntu
12.x (x64).

Python Setup
============
1. A working python 2.7.x install with support for virtualenv.

2. Create a virtualenv for use with this project. Use PIP and the project's requirements.txt file to configure the
virtualenv.

virtualenv aws-provisioning-env
source aws-provisioning-env/bin/activate
pip install -r aws-provisioning/requirements.txt

The virtual environment contains the project's dependencies including Boto and Fabric.

AWS Setup
=========
1. A valid AWS account with API and Secret Keys is required.
2. Create a SSH Key Pair for each region(s) which will be used to store AMIs and run instances.
3. Copy the private key to your local machine's "ssh" directory (~/.ssh on Linux)
4. Create S3 Buckets in each region which will be used. These buckets are used to store Cloud Formation templates.
5. Create a "default" and "mongodb" security group in the appropriate region(s). Note: "default" should already exist.
The mongodb security group needs to support ports 22 externally and 27017 within the security group.

Project Configuration
=====================
Update configuration settings in configuration.py
1. Set AWS_API_KEY and AWS_SECRET_KEY to the appropriate values for your AWS account.
2. Set AWS_KEY to the name of the AWS SSH Key Pair.
3. Set AWS_REGIONS to the list of regions supported
4. Set AWS_CF_S3_BUCKETS to the list of S3 bucket names used to store Cloud Formation templates.


Fabric Tasks
============
Fabric Tasks are executed within the Virtual Environment. To activate the virtual environment:
source aws-provisioning-env/bin/activate

Fabric Task arguments may be listed by position or by name. All Fabric arguments are converted to strings. Arguments
containing ',' or ' ' are enclosed within single quotes. Additionally, ',' are escaped using a '\'.

List Fabric tasks:
fab --list

Create Mongo AMIs in the us-west-2 region:
fab create_ami:aws_regions='us-west-2', ami_type:'mongo', ami_name:'MONGO_AMI', ami_description:'MONGO AMI'

Create Mongo AMIs in the us-west-2 and us-east-1 regions:
fab create_ami:aws_regions='us-east-1\,us-west-2', ami_type:'mongo', ami_name:'MONGO_AMI', ami_description:'MONGO AMI'

Publish Cloud Formation templates to S3 Buckets:
fab push_cf_templates_to_s3

Configure all instances tagges as 'or-mongo' within a us-west-2:
fab configure_instances:aws_region='us-west-2', aws_tag='or-mongo'

MongoDB Tasks
=============
Once the instances are configured, using Fabric, the ReplicaSet can be configured.
1. Log into each node and start MongoDB using:
service mongodb start

It may be a minute or two before the db is available to accept requests. Tail the log file to monitor the startup
progress:
tail -f /var/log/mongodb/mongodb.log

2. From the primary node, execute the following commands in the MongoDB javascript shell (/opt/mongodb/bin/mongo):
rs.initiate();

rs.add("<public dns  of secondary node>:27017");
rs.addArb("<public dns of arbiter>:27017");

A rs.status() command will display all of the nodes in the replica set. At this point the primary node is using it's
internal dns name, which will not persist if the instance is stopped and restarted. Reconfigure the primary member to
use it's public dns name and <a href="http://docs.mongodb.org/manual/reference/replica-configuration/#usage">update the replica set configuration.</a>