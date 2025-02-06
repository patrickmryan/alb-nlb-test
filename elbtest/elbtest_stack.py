from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    # aws_elasticloadbalancingv2_targets as elb_targets,
    aws_autoscaling as autoscaling,
)
from constructs import Construct


class ElbtestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        http_port = 80

        vpc_name = self.node.try_get_context("VpcName")

        vpc = ec2.Vpc.from_lookup(
            self,
            "Vpc",
            vpc_name=vpc_name,
        )

        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Vpc

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            """
yum update -y
yum install httpd -y
host=$(curl http://169.254.169.254/latest/meta-data/local-hostname)
cat > /var/www/html/index.html <<__EOF__
<title>$host</title>
hello from $host
__EOF__
service httpd start
"""
        )

        intra_vpc = ec2.Peer.ipv4(vpc.vpc_cidr_block)

        asg_subnets = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            availability_zones=(self.availability_zones)[:2],
        )

        template_sg = ec2.SecurityGroup(self, "WebServerSG", vpc=vpc)

        template = ec2.LaunchTemplate(
            self,
            "WebServer",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.SMALL
            ),
            # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/MachineImage.html
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(40, delete_on_termination=True),
                )
            ],
            # role
            security_group=template_sg,
            user_data=user_data,
        )

        template_sg.connections.allow_from(intra_vpc, ec2.Port.tcp(http_port))
        template_sg.connections.allow_from(intra_vpc, ec2.Port.tcp(22))

        # showing the ability to include more than one security group
        # in a launch template
        test_sg = ec2.SecurityGroup(self, "TestSG", vpc=vpc)
        test_sg.connections.allow_from(intra_vpc, ec2.Port.tcp(http_port))
        template.connections.add_security_group(test_sg)


        alb = elbv2.ApplicationLoadBalancer(self, "ALB",
            vpc=vpc,
            internet_facing=True
        )

        application_target_group = elbv2.ApplicationTargetGroup(
            self,
            "ALBtargetgroup",
            port=80,
            vpc=vpc,
            target_type=elbv2.TargetType.INSTANCE,
        )

        asg = autoscaling.AutoScalingGroup(
            self,
            "ASG",
            vpc=vpc,
            vpc_subnets=asg_subnets,
            launch_template=template,
            min_capacity=2,
            max_capacity=4,
            # max_instance_lifetime=Duration.days(14),
            # associate_public_ip_address=False,
            health_check=autoscaling.HealthCheck.ec2(),
            group_metrics=[autoscaling.GroupMetrics.all()],
            update_policy=autoscaling.UpdatePolicy.rolling_update(),
        )
        asg.attach_to_application_target_group(application_target_group)

        alb_listener = alb.add_listener(
            "ALBlistener",
            port=http_port,
            default_action=elbv2.ListenerAction.forward([application_target_group]),
            protocol=elbv2.ApplicationProtocol.HTTP   # elbv2.Protocol.TCP,
        )

        # nlb = elbv2.NetworkLoadBalancer(
        #     self, "NLB", vpc=vpc, internet_facing=False, vpc_subnets=asg_subnets
        # )


        # network_target_group = elbv2.NetworkTargetGroup(
        #     self,
        #     "NLBtargetgroup",
        #     port=80,
        #     vpc=vpc,
        #     target_type=elbv2.TargetType.ALB,
        # )


        # listener = nlb.add_listener(
        #     "NLBlistener",
        #     port=http_port,
        #     default_action=elbv2.NetworkListenerAction.forward([network_target_group]),
        #     protocol=elbv2.Protocol.TCP,
        # )
