__author__ = 'Dixon Whitmire'

# AWS KEY SETTINGS
AWS_API_KEY = ''
AWS_SECRET_KEY = ''
AWS_KEY_FILE = ''
LOCAL_AWS_KEY_FILE = '~/.ssh/' + AWS_KEY_FILE

#AMI SETTINGS
# Ubuntu 12.x EBS Backed Instances
# AMI IDs are available on http://cloud.ubuntu.com/ami/
AMI_ID_BY_REGION = {
    'us-east-1': 'ami-a29943cb',
    'us-west-1': 'ami-87712ac2',
    'us-west-2': 'ami-20800c10'
}

AMI_SECURITY_GROUP = 'default'
AMI_TYPES = ('mongo',)
AWS_USER_NAME = 'ubuntu'

# AWS REGION AND CLOUD FORMATION SETTINGS
# Note: If a config contains a single item, a trailing ',' is required since the settings are tuples.
# Example: AWS_REGIONS =('us-east-1',)
# AWS Region Identifiers
AWS_REGIONS = ()
# AWS S3 Bucket Names (Used for Cloud Formation)
AWS_CF_S3_BUCKETS = ()


# MONGO CONFIGURATIONS
MONGO_AMI_TYPE = 'mongo'
MONGODB_DOWNLOAD = 'http://fastdl.mongodb.org/linux/mongodb-linux-x86_64-2.2.0.tgz'
MONGODB_USER = 'mongodb'
MONGODB_GROUP = 'nogroup'

