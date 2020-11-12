try:
	import argparse
	from dgnutils import notify, log_level
	from instance_manager_functions import run_server
except Exception as e:
	print('Could not complete imports, are you running as `instance_monitor` conda environment?')
	print()
	raise e

log_level('i')

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Instance Manager Server')
	parser.add_argument('-s', '--daily_spend_threshold', action="store", type=int, help='amount above which notification happen frequently', default=0)
	parser.add_argument('-w', '--weekly_summary_day', action='store', type=int, help='days for summaries. 0 is sunday, 6 is saturday. use like -w 6 saturday notifications', default=None)
	parser.add_argument('-i', '--interval_mins', action="store", type=int, help='amount of time between checks', default=60)
	parser.add_argument('-t', '--daily_summary_times', nargs='*', type=int, help='times for summaries. use like -t 6 22 for 6am and 10pm notifications', default=[])
	args = parser.parse_args()
	try:

		run_server(
				daily_spend_threshold=args.daily_spend_threshold, 
				daily_summary_times=args.daily_summary_times, 
				interval_mins=args.interval_mins,
				weekly_summary_day=args.weekly_summary_day,
		)
		#print(args.daily_spend_threshold)
	except Exception as e:
		notify(f'Instance manager server has shutdown! {e}')
