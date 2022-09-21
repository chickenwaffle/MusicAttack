#! /usr/bin/env python
######################################################################
# tuner.py - a minimal command-line guitar/ukulele tuner in Python.
# Requires numpy and pyaudio.
######################################################################
# Author:  Matt Zucker
# Date:    July 2016
# License: Creative Commons Attribution-ShareAlike 3.0
#          https://creativecommons.org/licenses/by-sa/3.0/us/
######################################################################

import numpy as np
import pyaudio
import keyboard

import os       #os.getenv()
from os.path import exists
import time     #time.sleep()
import json

FSAMP = 48000       # Sampling frequency in Hz
FRAME_SIZE = 48000//60   # How many samples per frame? as much as we can get in 1/60th of a second
FRAMES_PER_FFT = 1  # FFT takes average across how many frames? (number of frames to delay for better accuracy)

SAMPLES_PER_FFT = FRAME_SIZE*FRAMES_PER_FFT

######################################################################
# For printing out notes

NOTE_NAMES = 'C C# D D# E F F# G G# A A# B'.split()


######################################################################
# These three functions are based upon this very useful webpage:
# https://en.wikipedia.org/wiki/Piano_key_frequencies
def freq_to_number(f):
    return 12*np.log2(f/440.0) + 49


def number_to_freq(n):
    return 440 * 2.0**((n-49)/12.0)


def note_name(n):
    return NOTE_NAMES[(n - 4) % 12] + str(int((n + 8) / 12))

######################################################################
fourier_array = (-2 * np.pi / FSAMP) * np.arange(SAMPLES_PER_FFT)
piano_frequencies = [number_to_freq(i) for i in np.arange(1, 89)]


def discrete_fourier_transform(f, samples):
    fourier_array_times_freq = f * fourier_array
    #return np.absolute(np.sum(samples * np.exp(1j * fourier_array_times_freq))) / samples.size
    x = np.sum(samples * np.cos(fourier_array_times_freq))
    y = np.sum(samples * np.sin(fourier_array_times_freq))
    return np.sqrt(x*x+y*y) / samples.size


def get_dominant_pitch(samples):
    response = [discrete_fourier_transform(f, samples) for f in piano_frequencies]
    max_index = np.argmax(response)
    return piano_frequencies[max_index], response[max_index]
######################################################################

# Calculate note returns position on an 88-key piano.
# An A440 will return the value 49.
# Result can be passed as an arg thru function note_name() to get note name, i.e. A4
def calculate_note():
    # Shift the buffer down and new data in
    buf[:-FRAME_SIZE] = buf[FRAME_SIZE:]
    buf[-FRAME_SIZE:] = np.frombuffer(stream.read(FRAME_SIZE), np.int16)

    # Run the DFFT on the buffer
    dominant_frequency, amplitude = get_dominant_pitch(buf)# * window)

    # Return 0 if sound isn't loud enough.
    if amplitude < 300:
        return 0

    # Get note number and nearest note
    n = freq_to_number(dominant_frequency)
    n0 = int(round(n))

    return n0

######################################################################
# Functions relating to panel attack and key assignment

# Grab keysV2.txt as JSON and import them
# Pulls keybindings on first configuration
# Returns dictionary containing keybindings
def get_panelattack_keys():
    btn_assignments={}

  # Load keys from file
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

# Attempt to load config.json. If fails, 
def load_config(panelattack_keys):
    note_key_dict = {}
    key_list = list(panelattack_keys.values())
    configfile = "config.json"

    try:
        with open(configfile) as f:
            note_key_dict = json.load(f)

        return note_key_dict

    except json.JSONDecodeError:
        print("Error: Invalid config.json file. Exiting.")
        exit()

    # TODO: Key binding should be done in a function separate from this
    except FileNotFoundError:
        print("No config file detected. Create one now? (Y/n) ", end='')
        option = ''
        try:
            option = input()
        except:
            print("Error: incorrect input.")
            exit()

        if option.lower() == "y" or option.lower() == "yes" or option == "":
            # Used to iterate thru key_list
            # Since Python doesn't like to convert dict values into lists and vice versa
            pos = 0

            # For each button, record 15 samples to find most
            # commonly occuring note.  Returns all keys as dict when done.
            for pa_key in panelattack_keys:
                recorded_notes = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
                i = 0

                while (i < len(recorded_notes)):
                    print("\r" + str(pa_key) + "                   ", end='')
                    recorded_notes[i] = calculate_note()

                    if recorded_notes[i] == 0:
                        i = 0
                    else:
                        print("\r" + str(pa_key) + "\tBinding...", end='')
                        i += 1

                    time.sleep(0.1)

                note_mode = mode(recorded_notes)
                note = note_name(note_mode)
                note_key_dict[note] = key_list[pos]

                print("\r" + str(pa_key) + "\tBound freq " + note + " to button \'" + key_list[pos] + "\'")

                pos += 1

            
            option = input("Save keybindings? (Y/n) ")
            if option.lower() == "y" or option.lower() == "yes" or option == "":
                with open(configfile,"a") as f:
                    json.dump(note_key_dict, f)

            return note_key_dict

        else:
            print("Exiting.")
            exit()

# Called in main() as the loop that translates notes to key inputs to Panel Attack
# Argument note_name_to_key takes dictionary.
def panel(stream, note_name_to_key):
    is_pressed = False

    while stream.is_active():
        freq = calculate_note()

        try:
            kbpress = note_name_to_key[ note_name(freq) ]
            if not is_pressed:
                keyboard.send(kbpress)
                print(str(kbpress))

            is_pressed = True

        except KeyError:
            is_pressed = False


######################################################################
# Functions relating to menu and interface

######################################################################

# Ok, ready to go now.

if __name__ == "__main__":

    # Allocate space to run an FFT.
    buf = np.zeros(SAMPLES_PER_FFT, dtype=np.float32)
    num_frames = 0

    # Initialize audio
    stream = pyaudio.PyAudio().open(format=pyaudio.paInt16,
                                    channels=1,
                                    rate=FSAMP,
                                    input=True,
                                    frames_per_buffer=FRAME_SIZE)

    stream.start_stream()

    prev_note = None
    note_name_to_key = None

    panelattack_keys = get_panelattack_keys()
    note_name_to_key = load_config(panelattack_keys)

    panel(stream, note_name_to_key)