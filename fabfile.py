""" fabfile.py

"""
__author__ = 'Dixon Whitmire'
import os
from time import sleep

from fabric.api import task, settings, sudo, execute
from fabric.contrib.files import upload_template, put
from boto.ec2 import EC2Connection, get_region, connect_to_region
from boto.ec2.blockdevicemapping import BlockDeviceMapping, BlockDeviceType
from boto.s3.connection import S3Connection
from boto.s3.key import Key


import configuration as config

@task
def create_ami(aws_regions, ami_type, ami_name, ami_description, root_device='/dev/sda1', root_device_size=25):
    """ Creates an EBS backed AMI in one or more AWS regions.

    parameters:
    aws_regions -- Comma delimited list of AWS regions, or single item listing, where the AMI is saved.
    ami_type -- The type of AMI to create. The ami_type determines how the AMI is configured.
    ami_name -- The name to save the AMI under. AMI names are unique within a region.
    ami_description -- The AMI's description.
    root_device -- The device mapping for the AMI's root volume. The AWS device mapping may differ from the device mapping
    used in the virtualized OS. Defaults to /dev/sda1.
    root_device_size -- The size of the root EBS volume in GB.
    """

    if ',' in aws_regions:
        aws_region_list = aws_regions.split(',')
    else:
        aws_region_list = [aws_regions]

    for aws_region in aws_region_list:

        if aws_region not in config.AWS_REGIONS:
            print('Unknown region {0}'.format(aws_region))
            continue

        if ami_type not in config.AMI_TYPES:
            raise ValueError('Unknown AMI Type {0}'.format(ami_type))

        ec2_connection = _get_ec2_connection(aws_region)

        print('Connected to {0}'.format(ec2_connection))

        ami_id = config.AMI_ID_BY_REGION[ec2_connection.region.name]

        root_ebs_device_mapping = _get_block_device_mapping(root_device, root_device_size)

        reservation = ec2_connection.run_instances(ami_id, key_name=config.AWS_KEY_FILE,
            security_group_ids=[config.AMI_SECURITY_GROUP], block_device_map=root_ebs_device_mapping)

        template_instance = reservation.instances[0]

        print('spinning up the instance')
        sleep(10)

        template_instance.update()

        while template_instance.state != 'running':
            sleep(10)
            template_instance.update()

        print('configuring instance {0}'.format(template_instance.id))

        with settings(host_string=template_instance.public_dns_name, key_filename=config.LOCAL_AWS_KEY_FILE,
            user=config.AWS_USER_NAME, connection_attempts=10):

            _configure_packages()

            if ami_type == 'mongo':
                _configure_mongo()

        # create the AMI based off of our instance
        print('Creating AMI {0}'.format(ami_name))
        new_ami_id = ec2_connection.create_image(template_instance.id, ami_name, ami_description)

        print('Creating new AMI for {0}. AMIID: {1}'.format(ami_name, new_ami_id))
        new_ami = ec2_connection.get_all_images([new_ami_id])[0]
        sleep(20)

        while (new_ami.state == 'pending'):
            new_ami.update()
            sleep(20)

        print('AMI Created')

        ec2_connection.create_tags([new_ami.id], {'Name': ami_name})

        # clean up
        print('Terminating instance')

        while template_instance.state != 'running':
            template_instance.update()
            sleep(20)

        ec2_connection.terminate_instances([template_instance.id])


def _get_ec2_connection(aws_region):
    """ Creates an EC2 Connection for the specified region.

    parameters:
    aws_region -- the aws region code (us-east-1, us-west-1, etc)
    """
    return connect_to_region(aws_region, aws_access_key_id=config.AWS_API_KEY, aws_secret_access_key=config.AWS_SECRET_KEY)

def _get_block_device_mapping(device_name, size):
    """ Returns a block device mapping object for the specified device and size.

    Block Device Mapping is used to associate a device on the VM with an EBS Volume.

    parameters:
    device_name -- The name of the device in the VM, such as /dev/sda1, /dev/sdb1. etc
    size -- The amount of space to allocate for the EBS drive.

    """
    block_device = BlockDeviceType()
    block_device.size = size
    bdm = BlockDeviceMapping()
    bdm[device_name] = block_device

    return bdm

def _configure_packages():
    """ Configures packages on the virtual OS.

    """
    sudo('apt-get update')
    sudo('apt-get upgrade --assume-yes')
    sudo('apt-get install lvm2 --assume-yes')
    sudo('apt-get install mdadm --assume-yes')

def _configure_mongo():
    """ Configures software for the Mongo AMI.

    MongoDB binaries are installed to /opt/mongodb.
    Logs are generated in /var/log/mongodb/mongodb.log
    The MongoDB process runs as the mongodb user.

    """
    # install binaries
    sudo('curl "{0}" > /opt/mongodb.tar.gz'.format(config.MONGODB_DOWNLOAD))
    sudo('tar -C /opt -xvf /opt/mongodb.tar.gz')
    sudo('ln -s /opt/mongodb-linux-x86_64-2.2.0 /opt/mongodb')
    sudo('rm /opt/mongodb.tar.gz')
    sudo('echo "export PATH=$PATH:/opt/mongodb/bin" >> /home/{0}/.bashrc'.format(config.AWS_USER_NAME))

    # write configuration file
    sudo('touch /etc/mongodb.conf')
    sudo('echo "logpath=/var/log/mongodb/mongod.log" >> /etc/mongodb.conf')
    sudo('echo "logappend=true" >> /etc/mongodb.conf')

    # set up logging
    sudo('mkdir -p /var/log/mongodb')
    sudo('touch /var/log/mongodb/mongod.log')

    # add the mongodb user
    sudo('useradd {0}'.format(config.MONGODB_USER))
    sudo('chown -R {0}:{1} /opt/mongodb*'.format(config.MONGODB_USER, config.MONGODB_GROUP))

@task
def push_cf_templates_to_s3(template_dir='cloudformation'):
    """ Pushes PD Cloud Formation templates up to AWS S3 Buckets.

     Cloud Formation uses S3 for template storage. Cloud Formation and it's backing S3 storage is region specific.
     This task publishes template updates to the backing S3 buckets. Use this function to "publish" new template
     updates and fixes.

     parameters:
     template_dir -- The local directory where the Cloud Formation templates are stored
    """

    abs_template_dir = os.path.abspath(template_dir)

    templates = []

    for file in os.listdir(abs_template_dir):

        if 'cf-template.json' != file:
            templates.append(os.path.join(abs_template_dir, file))

    print('Uploading templates:')
    print(templates)


    s3_conn = S3Connection(config.AWS_API_KEY, config.AWS_SECRET_KEY)

    for bucket_name in config.AWS_CF_S3_BUCKETS:
        bucket = s3_conn.get_bucket(bucket_name)

        for k in bucket.get_all_keys():
            k.delete()

        for t in templates:
            k = Key(bucket)
            k.key = os.path.basename(t)
            k.set_contents_from_filename(os.path.abspath(t))

    print('Upload complete')

@task
def configure_instances(aws_region, aws_tag):
    """ Configures a tagged AWS instance for use.

    General configuration tasks include RAID configuration.
    Specific tasks are executed based on the AWS "Name" tag

    parameters:
    aws_region -- The AWS region identifier code (us-east-1, us-west-1, us-west-2, etc)
    aws_tag -- The AWS "Name" tag
    """
    ec2_conn = _get_ec2_connection(aws_region)
    reservation = ec2_conn.get_all_instances(filters={'instance-state-name': 'running', 'tag:Name': '{0}'.format(aws_tag)})

    for r in reservation:
        for i in r.instances:
            # tag elastic ips so we can associate it on startup
            elastic_ips = ec2_conn.get_all_addresses(filters={'instance-id':i.id})
            if len(elastic_ips) > 0 and i.tags.get('ElasticIP') is not None:
                i.add_tag('ElasticIP', elastic_ips[0].public_ip)

            with settings(host_string=i.public_dns_name, key_filename=config.LOCAL_AWS_KEY_FILE,
                user=config.AWS_USER_NAME,connection_attempts=10):

                # configure storage (raid vs epehemeral)
                put('uploads/configure-raid.py', '/tmp/configure-raid.py', use_sudo=True)

                raid_level = i.tags.get('RaidLevel')
                attached_devices = i.tags.get('AttachedDevices')

                print('Configuring storage')
                if attached_devices is not None:
                    if raid_level is not None:
                        sudo('python /tmp/configure-raid.py {0} {1}'.format(raid_level, attached_devices))
                    else:
                        _mount_ebs_volume(attached_devices, '/mnt/ebs')

                # node specific configurations
                # note that we're using the name to drive the configuration
                name_tag = i.tags.get('Name')

                if 'mongo' in name_tag.lower():
                    execute(_configure_mongo_instance, i)

def _configure_mongo_instance(ec2_instance):
    """ Configures a mongo instance for use in the PD Stack.

    Configures RAID volumes, configuration files, etc.

    parameters:
    ec2_instance -- the MongoDB EC2 Instance to configure.
      Tags on the MongoDB Instance Include:
         Name: [region code]_[environment code]_MONGO
         RaidLevel: None or raid-0, raid-10
         AttachedDevices: None or /dev/xvdf,/dev/xvdg.etc
         NodeType: Arbiter, StandAlone, DataNode
         ElasticIP: None or ElasticIP Address bound to the instance
    """
    # use ebs attached devices if present otherwise plop the data on the ephemeral drive
    raid_level = ec2_instance.tags.get('RaidLevel')
    db_path = '/mnt/ebs/mongodb/data' if raid_level is not None else '/mnt/mongodb/data'

    # configure permissions for mongo directories
    sudo('mkdir -p {0}'.format(db_path))
    sudo('chown -R mongodb:nogroup {0}'.format(db_path))
    sudo('chown -R mongodb:nogroup /var/log/mongodb')

    # upload files
    put('uploads/mongodb',
        '/etc/init.d/mongodb',
        use_sudo=True
    )
    sudo('chmod u+x /etc/init.d/mongodb')

    sudo('echo "dbpath={0}" >> /etc/mongodb.conf'.format(db_path))

    aws_tag_name = ec2_instance.tags.get('Name')
    sudo('echo "replSet={0}" >> /etc/mongodb.conf'.format(aws_tag_name))

def _mount_ebs_volume(ebs_device, target_mnt_point, file_system='ext4'):
    """ Mounts and configures an EBS volume for use on the local file system.

    Parameters:
    ebs_device -- the ebs device (/dev/xvdf. /dev/xvdg, etc)
    target_mnt_point -- the mount point for the EBS device. The mount point is created if it does not exist.
    file_system -- the file system to use on the device. Defaults to ext4

    Returns the target mount point (string)
    """

    sudo('mkfs -t {0} {1}'.format(file_system, ebs_device))

    if not os.path.exists(target_mnt_point):
        sudo('mkdir -p {0}'.format(target_mnt_point))

    sudo('mount {0} {1}'.format(ebs_device, target_mnt_point))

    sudo('echo "{0} {1} {2} defaults,auto,noatime,noexec 0 0" | sudo tee -a /etc/fstab'.format(ebs_device, target_mnt_point, file_system))

    return target_mnt_point



