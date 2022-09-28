#! /usr/bin/env python
######################################################################
# MusicAttack.py - Use your musical instrument or voice to control panel attack
# Requires numpy, pyaudio, and keyboard.
######################################################################
# Author:  kornflakes, Sankyr
# Date:    August 2022
# License: MIT License 2022
#          https://mit-license.org/
######################################################################
import numpy as np
import pyaudio
import keyboard

import os       #os.getenv()
from os.path import exists
import time     #time.sleep()
import json

# Input Processing Utilities
#
# 
class IPU:
    __pyaud = None
    stream = None

    DEFAULT_FSAMP = 48000
    DEFAULT_FRAME_SIZE = 800
    DEFAULT_FRAMES_PER_FFT = 1
    DEFAULT_MIC_INDEX = 0
    DEFAULT_SENSITIVITY = 300
    NOTE_NAMES = 'C C# D D# E F F# G G# A A# B'.split()
    MONO = 1

    fsamp = 0
    frame_size = 0
    frames_per_fft = 0
    mic_index = -1
    sensitivity = 0
    samples_per_fft = 0
    amplitude = 0.0
    buf = None
    note = 0
    note_name = ""
    fourier_array = None
    piano_frequencies = None

    def __init__(self):
        self.__pyaud = pyaudio.PyAudio()
        self.fsamp = self.DEFAULT_FSAMP
        self.frame_size = self.DEFAULT_FRAME_SIZE
        self.frames_per_fft = self.DEFAULT_FRAMES_PER_FFT
        self.samples_per_fft = self.frame_size * self.frames_per_fft
        self.mic_index = self.DEFAULT_MIC_INDEX
        self.sensitivity = self.DEFAULT_SENSITIVITY

        self.fourier_array = (-2 * np.pi / self.fsamp) * np.arange(self.samples_per_fft)
        self.piano_frequencies = [self.number_to_freq(i) for i in np.arange(1, 89)]
    
    
    def get_pyaudio(self):
        return(self.__pyaud)

    def get_stream(self):
        return(self.stream)

    def get_sample_size(self):
        return(self.sample_size)
    
    def get_amplitude(self):
        return(self.amplitude)

    def get_sensitivity(self):
        return(self.sensitivity)
    
    def get_sampling_rate(self):
        return(self.sampling_rate)  

    def get_note(self):
        return(self.note)

    def get_note_name(self):
        return(self.note_name)

    def get_mic_index(self):
        return(self.mic_index)
    
    def set_sample_size(self, size):
        self.sample_size=size
        self.start()
    
    def set_sampling_rate(self, rate):
        self.sampling_rate=rate  
        self.start()


    def start(self):
        if(self.stream):
            self.stop()  
        if(not self.mic_index):
            self.mic_index=int(self.get_pyaudio().get_default_input_device_info()["index"])
            #print(self.mic_index)
            self.set_sampling_rate(int(self.get_pyaudio().get_device_info_by_index(self.mic_index)["defaultSampleRate"]))
            #print(self.getSamplingRate())
        try:
            self.buf = np.zeros(self.samples_per_fft, dtype=np.float32)
            self.stream=self.get_pyaudio().open(format=pyaudio.paInt16,
                                               channels=self.MONO,
                                               input_device_index=int(self.mic_index),
                                               rate=self.fsamp,
                                               input=True,
                                               frames_per_buffer=self.frame_size)
        except OSError:
            print("Error: Microphone did not properly initialize.\nPlease check if you are using correct microphone index and try again.\n")
            exit()

    def stop(self):
        self.stream.stop_stream()
        self.stream.close() 

    def implode(self):   
        self.stop()
        self.get_pyaudio().terminate()
    
    def toggle(self):
        if(self.stream):
            self.stop()
        else:
            self.start()

    ######################################################################
    # These three functions are based upon this very useful webpage:
    # https://en.wikipedia.org/wiki/Piano_key_frequencies
    def freq_to_number(self, f):
        return 12*np.log2(f/440.0) + 49


    def number_to_freq(self, n):
        return 440 * 2.0**((n-49)/12.0)


    def note_to_note_name(self, n):
        return self.NOTE_NAMES[(n - 4) % 12] + str(int((n + 8) / 12))



    ######################################################################



    def discrete_fourier_transform(self, f, samples):
        fourier_array_times_freq = f * self.fourier_array
        #return np.absolute(np.sum(samples * np.exp(1j * fourier_array_times_freq))) / samples.size
        x = np.sum(samples * np.cos(fourier_array_times_freq))
        y = np.sum(samples * np.sin(fourier_array_times_freq))
        return np.sqrt(x*x+y*y) / samples.size


    def get_dominant_pitch(self, samples):
        response = [self.discrete_fourier_transform(f, samples) for f in self.piano_frequencies]
        max_index = np.argmax(response)
        return self.piano_frequencies[max_index], response[max_index]
    ######################################################################

    def get_microphone_list(self):
        retval={}
        adict=None
        for devindex in range(self.get_pyaudio().get_device_count()):
            adict=self.get_pyaudio().get_device_info_by_index(devindex)
            if(bool(int(adict["maxInputChannels"]))):
                retval[adict["name"]]=adict["index"]
        return(retval)     

    def get_microphone_name(self):
        # Cancel if microphone is not set
        if self.mic_index == -1:
            return("NULL")

        retval={}
        adict=self.get_microphone_list()

        for key, value in adict.items():
            if value == self.mic_index:
                return(key)

    def set_microphone_index(self, index):
        self.mic_index=index
        if(self.stream):
            self.stop()

    # If no argument is given to set_microphone, then
    # interactively prompt the user to select a microphone from a list
    def set_microphone(self):
        inputs = self.get_microphone_list()
        print("\n#\tInput\n========================================")
        for key, value in inputs.items():
            print(str(value) + "\t" + key)

        self.mic_index = int(input("Select a microphone #: "))

    # Calculate note returns position on an 88-key piano.
    # An A440 will return the value 49.
    # Result can be passed as an arg thru function note_name() to get note name, i.e. A4
    def calculate_note(self):
        if(self.stream):
            # Shift the buffer down and new data in
            self.buf[:-self.frame_size] = self.buf[self.frame_size:]
            self.buf[-self.frame_size:] = np.frombuffer(self.stream.read(self.frame_size), np.int16)

            # Run the DFFT on the buffer
            self.dominant_frequency, self.amplitude = self.get_dominant_pitch(self.buf)# * window)

            # Return 0 if sound isn't loud enough.
            #TODO: Move this to somewhere else so that testing can be done properly.
            if self.amplitude < self.sensitivity:
                self.note_name = 0
                return
            else:
                # Get note number and nearest note
                n = self.freq_to_number(self.dominant_frequency)
                self.note = int(round(n))
                self.note_name = self.note_to_note_name(self.note)



    def test(self):
        self.start()
        while(self.stream.is_active()):
            try:
                self.calculate_note()
                print("\rMIDI:\t{}\t\tNote:\t{}  \t\tAmpl:\t{}    ".format(self.note, self.note_name, self.amplitude), end="")
            except KeyboardInterrupt:
                break
        self.stop()
######################################################################
# Functions relating to Panel Attack and config loading/creation

# Grab keysV2.txt as JSON and import them
# Pulls keybindings on first configuration
# Returns dictionary containing keybindings
def get_panelattack_keys():
    btn_assignments={}

  # Load keys from file
    #TODO: Cross-platform the following lines
    APPDATA = os.getenv("APPDATA")
    keys_file = "\Panel Attack\keysV2.txt" 
    KEYS_PATH = APPDATA + keys_file

    try:
        with open(KEYS_PATH) as file:
            loaded_file = json.load(file)

            btn_assignments["swap1"] = str(loaded_file[0]["swap1"])
            btn_assignments["raise1"] = str(loaded_file[0]["raise1"])
            btn_assignments["up"] = str(loaded_file[0]["up"])
            btn_assignments["down"]  = str(loaded_file[0]["down"])
            btn_assignments["left"] = str(loaded_file[0]["left"])
            btn_assignments["right"] = str(loaded_file[0]["right"])

            return btn_assignments
    except FileNotFoundError:
        print("Error: \'" + KEYS_PATH + "\' not found.\nPlease verify Panel Attack is installed and keyboard keys are set.\nExiting.\n")
        exit()

# Used in load_config() to find most frequently occuring note
def mode(ls):
    # dictionary to keep count of each value
    counts = {}
    # iterate through the list
    for item in ls:
        if item in counts:
            counts[item] += 1
        else:
            counts[item] = 1
    # get the key with the max count
    keys = [key for key in counts.keys() if counts[key] == max(counts.values())] 
    return(keys[0])

# Contains code to interactively create config.json
def create_config(configfile, ipu, panelattack_keys):
    new_config = {}

    ipu.set_microphone()
    new_config["mic_index"] = int(ipu.get_mic_index())

    # Create an index keys inside config dictionary
    new_config["keys"] = {}

    # Used to iterate thru key_list
    # Since Python doesn't like to convert dict values into lists and vice versa
    key_list = list(panelattack_keys.values())
    pos = 0

    ipu.start()

    # For each button, record 15 samples to find most
    # commonly occuring note.  Returns all keys as dict when done.
    print("Play a note for two seconds to bind it to the key:")
    for pa_key in panelattack_keys:
        recorded_notes = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
        i = 0

        while (i < len(recorded_notes)):
            print("\r" + str(pa_key) + "                              ", end='')
            ipu.calculate_note()
            recorded_notes[i] = ipu.get_note_name()

            if recorded_notes[i] == 0:
                i = 0
            else:
                print("\r" + str(pa_key) + "\tBinding...\t[" + str(i+1) + "/" + str(len(recorded_notes)) + "]", end='')
                i += 1
                time.sleep(0.1)


        note_mode = mode(recorded_notes)
        new_config["keys"][note_mode] = key_list[pos]

        print("\r" + str(pa_key) + "\tBound note " + note_mode + " to button \'" + key_list[pos] + "\'")

        pos += 1
    
    option = input("Save keybindings? (Y/n) ")
    if option.lower() == "y" or option.lower() == "yes" or option == "":
        with open(configfile,"w") as f:
            json.dump(new_config, f)

    ipu.stop()
    return new_config

# Attempt to load config.json. Returns as JSON.
# If config.json is not present in running directory,
# the program will call create_config() to make one.
def load_config(panelattack_keys):
    config = {}
    configfile = "config.json"

    try:
        with open(configfile) as f:
            config = json.load(f)

        return config

    except json.JSONDecodeError:
        print("Error: Invalid config.json file. Please delete config.json and run the program again.\nExiting.")
        exit()

    except FileNotFoundError:
        print("No config file detected. Create one now? (Y/n) ", end='')
        option = ''
        try:
            option = input()
        except:
            print("Error: incorrect input.")
            exit()

        if option.lower() == "y" or option.lower() == "yes" or option == "":
            return create_config(configfile, ipu, panelattack_keys)


        else:
            print("Exiting.")
            exit()

# Returns a string that can be outputted in console
def print_readable_panelattack_config(panelattack_keys, config):
    pa_keys = list(panelattack_keys.keys())
    notes = list(config["keys"].keys())

    for i in range(0, len(pa_keys)):
        print("\'{}\' is bound to key \'{}\' (note {})".format(pa_keys[i], config["keys"][notes[i]], notes[i]))

# Called in main() as the loop that translates notes to key inputs to Panel Attack
# Argument note_name_to_key takes dictionary.
def panel(ipu, config):
    print("Sound is now being translated to keys. Press Ctrl + C to stop.")
    ipu.start()

    is_pressed = False

    try:
        while ipu.get_stream().is_active():
            ipu.calculate_note()

            try:
                kbpress = config["keys"][ ipu.get_note_name() ]
                if not is_pressed:
                    keyboard.send(kbpress)
                    #print(str(kbpress))

                is_pressed = True

            except KeyError:
                is_pressed = False

    except KeyboardInterrupt:
        pass
    
    ipu.stop()


######################################################################
# Functions relating to menu and interface

banner = '''RECORDER ATTACK

          ___0~
            \ \/
              |
             / \\
             \  \\
             ~  ~
'''
def main_menu(ipu, config):
        while True:
            print("\n")
            print("1. Run")
            print("2. Reconfigure Input")
            print("3. Test microphone")
            print("0. Exit")

            choice = ""
            try:
                choice = int(input("Select and option: "))
            except:
                print("Error: Invalid input. Please enter a number.")


            if (choice == 1):
                panel(ipu, config)
            elif (choice == 2):
                configfile = "config.json"
                panelattack_keys = get_panelattack_keys()
                print("Your Microphone is set to {}".format(ipu.get_microphone_name()))
                print_readable_panelattack_config(panelattack_keys, config)
                
                verify = input("Are you sure you want to overwrite your settings? (y/N) ")
                if (verify.lower() == "yes" or verify.lower() == "y"):
                    create_config(configfile, ipu, panelattack_keys)
            elif (choice == 3):
                ipu.test()
            elif (choice == 0):
                print("Exiting.")
                exit()
######################################################################

# Ok, ready to go now.

def test(ipu):
   ipu.test() 

def main(ipu):
    panelattack_keys = get_panelattack_keys()
    config = load_config(panelattack_keys)

    # tell ipu which microphone to use after loading config
    # because problems happen if not
    ipu.set_microphone_index(config["mic_index"])
    
    # Menu loops
    main_menu(ipu, config)

if __name__ == "__main__":
    print(banner)
    ipu = IPU()

    # Uncomment test(ipu) to check microphone and see how the program calculates values
    #test(ipu)
    main(ipu)