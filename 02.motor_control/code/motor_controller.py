import sqlalchemy as sql
import sys
import serial
import numpy as np
import pandas as pd
from time import sleep

sys.path.insert(1, '/home/pi/automated_arc_tomography/02.motor_control/code/')

from SmcG2Serial import SmcG2Serial

# local or remote (PSI) mode
# MODE = "PSI"
MODE = "LOCAL"


# database connection
PATH_CREDENTIALS_PSI = '~/credentials.pw'
PATH_CREDENTIALS_LOCAL = '/Users/hkromer/02_PhD/01.github/FNL_Neutron_Generator_Control/credentials.pw'

PATH_CREDENTIALS = PATH_CREDENTIALS_PSI if MODE == 'PSI' else PATH_CREDENTIALS_LOCAL



# motor initialization
PORT_NAME = "/dev/ttyACM0"
BAUD_RATE = 9600
DEVICE_NUMBER = None



# connect to the database
def connect_database(path_credentials):
	"""
	Connects to the database using the credentials in the path_credentials specified.
	OUTPUT:
		- sql_engine
	"""
	# read password and user to database
	credentials = pd.read_csv(PATH_CREDENTIALS, header=0)

	user = str(credentials['username'].values[0])
	pw = str(credentials['password'].values[0])
	host = str(credentials['hostname'].values[0])
	db = str(credentials['db'].values[0])

	connect_string = 'mysql+pymysql://%(user)s:%(pw)s@%(host)s:3306/%(db)s'% {"user": user, "pw": pw, "host": host, "db": db}

	sql_engine = sql.create_engine(connect_string)

	return sql_engine



def initialize_motor(port_name, baud_rate, device_number=None, timeout=0.1, write_timeout=0.1):
	"""
	Initializes the motor

	INPUT:
		- port_name: serial port name, can be found via `ls /dev/tty*` if more than one is connected.
		- baud_rate: baud rate (bits per second).
		- device_number: chose if multiple SMCs are connected.

	RETURN:
		- smc object to control the motor
	"""
	port = serial.Serial(port_name, baud_rate, timeout=0.1, write_timeout=0.1)
	smc = SmcG2Serial(port, device_number)

	smc.exit_safe_start()


	return smc


def log_to_database(sql_engine, command, response):
	"""
	Sends to the database what the command was sent to the motor and what the response from the motor was.

	INPUT:
		- sql_engine: sql engine connection to database
		- command: command that was sent to the motor
		- response: response from the motor
	"""

	query = f"""INSERT INTO arc_motor_log (sent_to_motor, response) VALUES (\"{command}\", \"{response}\");"""
	sql_engine.execute(query)


def control_motor(sql_engine, speed, direction):
	"""
	Sends speed and direction to the motor and adds log to the database

	INPUT:
		- sql_engine: sql engine connection to database
		- speed: speed of motor
		- direction: direction of motor
	"""
	# ensure speed is positive
	speed = int(np.abs(speed))

	# limit speed to 3200 at most
	speed = np.max(speed, 3200)

	# if direction is negative, add make speed negative
	if direction < 0:
		speed = -speed

	# set the speed
	smc.set_target_speed(speed)

	# read error status
	error_status = smc.get_error_status()
	error_status = "0x{:04X}".format(error_status)

	# read target speed
	target_speed = smc.get_target_speed()

	# log into database
	command = f"Speed: {speed}"
	response = f"Speed: {target_speed}; Error: {error_status}"
	log_to_database(sql_engine, command, response)


def get_commands(sql_engine):
	"""
	Connects to the database and reads speed and direction to be set.

	INPUT:
		- sql_engine: connection to the database
	OUTPUT:
		- speed: speed of the motor
		- direction: negative number is negative direction, positive direction is positive number
	"""
	query = f"SELECT * FROM arc_motor_control"
	df = pd.read_sql(query, sql_engine)

	speed = df['speed'].values[0]

	direction = df['direction'].values[0]

	return speed, direction


while True:
	try:
		# connect to the database
		sql_engine = connect_database(PATH_CREDENTIALS)

		# Read direction and speed from DB
		speed, direction = get_commands(sql_engine)

		# Sends the Exit Safe Start command, which is required to drive the motor.
		smc.exit_safe_start()

		# Send to motor
		control_motor(sql_engine, speed, direction)

        sleep(1) # sleep for 1 second

	except KeyboardInterrupt:
		print('Ctrl + C. Exiting.')
		sys.exit(1)