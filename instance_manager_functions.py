try:
	import boto3, requests, json, logging, time as pytime, pytz
	from datetime import datetime, timezone
	from dgnutils import notify
	import googleapiclient.discovery
	compute = googleapiclient.discovery.build('compute', 'v1')

	ec2 = boto3.client('ec2')
	pricing = boto3.client('pricing') # create the client
	ssm = boto3.client('ssm')

	logging.basicConfig(
		format='%(asctime)s %(levelname)-8s %(message)s',
		level=logging.INFO,
		datefmt='%Y-%m-%d %H:%M:%S'
	)
except Exception as e:
	print('Could not complete imports, are you running as boto3 conda environment?')
	print()
	raise e

class Regions:
	@classmethod
	def get_regions(cls):
		short_codes = cls._get_region_short_codes()
		
		regions = [{
			'name': cls._get_region_long_name(sc),
			'code': sc
		} for sc in short_codes]

		regions_sorted = sorted(
			regions,
			key=lambda k: k['name']
		)

		return regions_sorted

	@classmethod
	def _get_region_long_name(cls, short_code):
		param_name = (
			'/aws/service/global-infrastructure/regions/'
			f'{short_code}/longName'
		)
		response = ssm.get_parameters(
			Names=[param_name]
		)
		return response['Parameters'][0]['Value']

	@classmethod
	def _get_region_short_codes(cls):
		output = set()
		for page in ssm.get_paginator('get_parameters_by_path').paginate(
			Path='/aws/service/global-infrastructure/regions'
		):
			output.update(p['Value'] for p in page['Parameters'])

		return output

regions = Regions.get_regions()
rn2rc = {r['name']: r['code'] for r in regions}; rn2rc
rc2rn = {r['code']: r['name'] for r in regions}; rc2rn;

def get_price(instance_type, region_name):
	"""
	:param instance_type is the type such as 't2.micro'
	:param region_name is the name such as 'US East (N. Virginia)'
	:return price (float)
	"""

	# Manage GCP instances through hard-coding
	if instance_type == 'n1-highmem-8' and 'us-east1' in region_name: # us-east1-c or us-east1-b
		logging.info('Returning hard-coded cost for n1-highmem-8 of 2.14')
		return 2.14 # Calced from billing

	response = pricing.get_products(
		ServiceCode='AmazonEC2',
		Filters=[
			{'Type': 'TERM_MATCH','Field': 'operation', 'Value': 'RunInstances'},
			{'Type': 'TERM_MATCH','Field': 'capacitystatus', 'Value': 'Used'},
			{'Type': 'TERM_MATCH','Field': 'operatingSystem', 'Value': 'Linux'},
			{'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type}, #'<insance_type>, e.g. r4.large
			{'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_name},
		],
	); response
	price_item = [json.loads(p) for p in response["PriceList"]]; price_item
	price = float(list(list(price_item[0]['terms']['OnDemand'].values())[0]['priceDimensions'].values())[0]['pricePerUnit']['USD']); price
	price_time_unit = list(list(price_item[0]['terms']['OnDemand'].values())[0]['priceDimensions'].values())[0]['unit']; price_time_unit
	if price_time_unit != 'Hrs': raise Exception('Price given is not in hours')
	return price

# To check for which instances are running and give info on them
def get_instance_details():    
	instance_details = []

	# Get AWS Info
	reservations = ec2.describe_instances().get('Reservations'); reservations#.keys()
	instances = [next(iter(i.get('Instances', {}))) for i in reservations]; instances
	for instance in instances:
		i_type = instance.get('InstanceType')
		r_name = [r['name'] for r in regions if r['code'] in instance['Placement']['AvailabilityZone']][0]
		name = next(iter([tag['Value'] for tag in instance.get('Tags') if tag.get('Key')=='Name']), None)#[?Key==`Name`].Value
		state = instance.get('State',{}).get('Name','')
		started = datetime.strftime(instance.get('LaunchTime'), '%y-%m-%d @ %T %Z')
		running = (datetime.now(instance.get('LaunchTime').tzinfo) - instance.get('LaunchTime')).days
		price = get_price(i_type, r_name)
		details = {
			'InstanceType': i_type, 
			'Started':started,
			'RunningDuration':running,
			'State':state,
			'Name':name,
			'Region':r_name,
			'Price':price
		}
		instance_details.append(details); instance_details

	# Get GCP Infoi
	gcp_project = 'fast-ai-course-v3-dnish123'
	zone_list = compute.instances().aggregatedList(project=gcp_project).execute()
	logging.info(f'Getting GCP information for {gcp_project} solely')
	for zone, data in zone_list['items'].items():
		if not 'instances' in data: continue
		for instance in data['instances']:	 
			i_type = instance['machineType'].split('/')[-1]
			r_name = zone.lstrip('zones/')
			details = {
				'InstanceType': i_type, 
				'Started':None,
				'RunningDuration':None,
				'State':instance['status'].lower(),
				'Name':instance['name'],
				'Region': r_name,
				'Price': get_price(i_type, r_name),
				}
			instance_details.append(details)

	return instance_details

def get_monthly_spend(instance_details):
	"""
	:param instance_details comes from get_instance_details and is a list of dicts
	"""
	monthly_spend = 0
	stopped_states = ['stopped', 'terminated', 'stopping']
	for d in instance_details:
		if not d['State'] in stopped_states:
			monthly_spend += d['Price'] * 24 * 30 
	return monthly_spend

def get_notification_message(instance_details):
	monthly_spend = get_monthly_spend(instance_details);
	notification_message = f'Expected cloud spend is ${round(monthly_spend,2)} / Month'
	for instance in instance_details:
		if instance['State'] != 'running': continue
		i_type = instance['InstanceType']
		price = round(instance['Price'], 3)
		name = instance['Name']
		running = instance['RunningDuration']
		notification_message += f"\n${price}: {i_type}, {name[:10]}- on {running} days"
	return notification_message

def run_server(daily_spend_threshold:int=0, daily_summary_times:list=[], interval_mins:int=60):
	"""
	:param daily_spend_threshold (int) number of dollars over which daily spend will be notified
	:param daily_summary_times (int list) 24hr times to log instances
	:param interval_mins is the number of minutes to wait between running this program
	"""
	logging.info('Version 1.0 - 08/30/20')
	logging.info(f'daily_spend_threshold: {daily_spend_threshold}, {type(daily_spend_threshold)}')
	logging.info(f'daily_summary_times: {daily_summary_times}, {type(daily_summary_times)}')
	logging.info(f'interval_mins: {interval_mins}, {type(interval_mins)}')
	
	# initialization
	past_notifications = {} # dict of dates and hours

	while True:
		now = datetime.now().astimezone(pytz.timezone('US/Eastern'))
		date = now.strftime('%m-%d'); date
		hour = int(now.strftime('%H')); hour

		# print(hour, type(hour))
		# print(daily_summary_times, type(daily_summary_times), type(daily_summary_times[0]))
		
		# Check if spending is above limit every interval_mins
		instance_details = get_instance_details()
		monthly_spend = get_monthly_spend(instance_details)
		if monthly_spend > daily_spend_threshold:
			logging.info(f'High cloud spend notification. {monthly_spend} spend > {daily_spend_threshold} threshold')
			notify(f"WARNING: High cloud spend\n {get_notification_message(instance_details)}")

		# If the time is right for a always-notify
		elif hour in daily_summary_times and hour not in past_notifications.setdefault(date, []): 
			# Do the notification
			logging.info(f'Summary notification at hour {hour}')
			notify(get_notification_message(instance_details))

			# Store
			past_notifications[date].append(hour)

		# print(f'Sleeping {60*interval_mins} seconds')
		pytime.sleep(60 * interval_mins)
		# print(f'done sleeping')
