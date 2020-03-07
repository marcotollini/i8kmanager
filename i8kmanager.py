import json
from subprocess import Popen, PIPE
import os
import re
import time
import sys


def error(err):
   global all_config

   try:
      Popen([all_config['i8kfan'], '2', '2'])
   except:
      exc_type, exc_value, exc_traceback = sys.exc_info()
      Popen(['i8kfan', '2', '2'])
   finally:
      print('!!FAN ERROR!! {}'.format(err))

      notify = Notify(all_config['notify'])
      notify.send('!!FAN ERROR!! {}'.format(err))

class Notify:
   def __init__(self, config):
      self.command = config['command']

   def send(self, msg):
      print(msg)
      os.system(self.command.format(msg))

class Battery:
   def get(self):
      p = Popen(['acpi'], stdout=PIPE, stderr=PIPE, stdin=PIPE)
      stdout = str(p.stdout.read())

      if 'Discharging' in stdout:
         return 'BATT'
      elif 'Charging' in stdout:
         return 'CHARGING'
      else:
         return 'AC'

# Uses class Battery
class Config:
   def __init__(self, config):
      self.config = config
      self.battery = Battery()

   def get(self):
      status = self.battery.get()
      return self.config[status]


class Temperature:
   def __init__(self, config):
      self.paths = []
      self.config = config
      regexp = re.compile(config["regex_folder"])
      main_path = config['main_path']

      for thermal_zone in os.listdir(main_path):
         if not regexp.search(thermal_zone):
            continue
         # the path contain regex, now check for the type of the sensors

         sensor_type_path = os.path.join(main_path, thermal_zone, 'type')

         fh = open(sensor_type_path, 'r')
         if fh.readline().rstrip('\n') in config['sensors_type']:
            sensor_temp_path = os.path.join(main_path, thermal_zone, 'temp')
            self.paths.append(sensor_temp_path)
         fh.close()

      if self.paths == []:
         error('Can\' find any of the sensors defined in config')
      else:
         print('{} sensors found out of {}'.format(len(self.paths), len(config['sensors_type'])))

   def get(self):
      temperatures = []

      for path in self.paths:
         fh = open(path, 'r')
         temperature = int(fh.readline().rstrip('\n')) / 1000
         temperatures.append(temperature)

      temperature = max(temperatures)
      if temperature <= self.config['min'] or temperature >= self.config['max']:
         error('temperature is out of bound ({}, {}). It is probably impossible to read the temperature. TEMP = {}'.format(self.config['min'], self.config['max'], temperature))

      return temperature


# Uses class Config, Notify, Temperature
class Fan:
   def __init__(self, all_config):
      i8kfan = all_config['i8kfan']
      noti = all_config['notify']
      ranges = all_config['ranges']
      sensors = all_config['sensors']

      self.i8kfan = i8kfan
      self.notify = Notify(noti)
      self.config = Config(ranges)
      self.temperature = Temperature(sensors)

      self.current = -1

   # set new fan speed via i8kfan
   def set(self, left, right):
      p = Popen([self.i8kfan, str(left), str(right)], stdout=PIPE, stderr=PIPE, stdin=PIPE)
      self.notify.send('Fan speed set to {} {}'.format(left, right))

   # return current status of fan
   def get(self):
      p = Popen([self.i8kfan], stdout=PIPE, stderr=PIPE, stdin=PIPE)
      stdout = str(p.stdout.read())
      [left, right] = re.findall(r'[\d.]+', stdout)
      return (int(left), int(right))

   # set new fan speed if necessary
   def set_new(self):
      prev = self.current
      (left, right) = self.get_new()
      (set_left, set_right) = self.get()

      if prev != self.current or set_left != left or set_right != right:
         self.set(left, right)

   # get new fan speed as a tuple
   def get_new(self):
      self.current = max(0, self.current)
      self.current = min(2, self.current)
      config = self.config.get()
      temperature = self.temperature.get()


      for i in range(20):
         mi = config[self.current]['min']
         ma = config[self.current]['max']

         if self.current > 0 and temperature < mi:
            # temperature is lower than min, lower fan speed
            self.current = self.current - 1
         elif self.current < len(config)-1 and temperature > ma:
            # temperature is too high, go to next step
            self.current = self.current + 1
         else:
            return (config[self.current]['left'], config[self.current]['right'])

      error("Program in loop")


try:
   # read config json
   with open('config.json', 'r') as config_json:
      all_config = json.load(config_json)

   fan = Fan(all_config)
   while True:
      fan.set_new()
      time.sleep(all_config['timeout'] / 1000)
except:
   exc_type, exc_value, exc_traceback = sys.exc_info()
   error('{} ({})'.format(exc_value, exc_type))