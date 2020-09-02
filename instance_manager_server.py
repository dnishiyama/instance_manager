try:
	import argparse
	from dgnutils import notify, log_level
	from instance_manager_functions import run_server
except Exception as e:
	print('Could not complete imports, are you running as py37 conda environment?')
	print()
	raise e

log_level('i')

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Instance Manager Server')
	parser.add_argument('-s', '--daily_spend_threshold', action="store", help='amount above which notification happen frequently', default=0)
	parser.add_argument('-t', '--daily_summary_times', nargs='*', help='times for summaries. use like -t 6 22 for 6am and 10pm notifications', default=[])
	parser.add_argument('-i', '--interval_mins', action="store", help='amount of time between checks', default=60)
	args = parser.parse_args()
	try:
		run_server(int(args.daily_spend_threshold), [int(d) for d in args.daily_summary_times], int(args.interval_mins))
		#print(args.daily_spend_threshold)
	except Exception as e:
		notify(f'Instance manager server has shutdown! {e}')
