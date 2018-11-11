#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Nov 10 12:06:46 2018

Taken from Hedonistr's Music Generation With Lstm blog post

"""

import zipfile
import glob

from pathlib import Path

import glob
import os
import music21
import numpy as np
import scipy as sp
import matplotlib.pyplot as plt
from music21 import converter, instrument, note, chord, duration, stream
print (music21.__version__) #if your version is lower than 4.x.x, you will encounter with some issues.

def note_to_int(note): # converts the note's letter to pitch value which is integer form.
    # source: https://musescore.org/en/plugin-development/note-pitch-values
    # idea: https://github.com/bspaans/python-mingus/blob/master/mingus/core/notes.py
    note_base_name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    if ('#-' in note):
        first_letter = note[0]
        base_value = note_base_name.index(first_letter)
        octave = note[3]
        value = base_value + 12*(int(octave)-(-1))
        
    elif ('#' in note): # not totally sure, source: http://www.pianofinders.com/educational/WhatToCallTheKeys1.htm
        first_letter = note[0]
        base_value = note_base_name.index(first_letter)
        octave = note[2]
        value = base_value + 12*(int(octave)-(-1))
        
    elif ('-' in note): 
        first_letter = note[0]
        base_value = note_base_name.index(first_letter)
        octave = note[2]
        value = base_value + 12*(int(octave)-(-1))
        
    else:
        first_letter = note[0]
        base_val = note_base_name.index(first_letter)
        octave = note[1]
        value = base_val + 12*(int(octave)-(-1))
        
    return value


# Lets determine our matrix's value 
# rest --> (min_value, lower_bound)
# continuation --> (lower_bound, upper_bound)
# first_touch --> (upper_bound, max_value)

min_value = 0.00
lower_first = 0.00

lower_second = 0.5
upper_first = 0.5

upper_second = 1.0
max_value = 1.0

def notes_to_matrix(notes, durations, offsets, min_value=min_value, lower_first=lower_first,
                    lower_second=lower_second,
                    upper_first=upper_first, upper_second=upper_second,
                    max_value=max_value):
    
    # I want to represent my notes in matrix form. X axis will represent time, Y axis will represent pitch values.
    # I should normalize my matrix between 0 and 1.
    # So that I will represent rest with (min_value, lower_first), continuation with [lower_second, upper_first]
    # and first touch with (upper_second, max_value)
    # First touch means that you press the note and it cause to 1 time duration playing. Continuation
    # represent the continuum of this note playing. 
    
    try:
        last_offset = int(offsets[-1]) 
    except IndexError:
        print ('Index Error')
        return (None, None, None)
    
    total_offset_axis = last_offset * 4 + (8 * 4) 
    our_matrix = np.random.uniform(min_value, lower_first, (128, int(total_offset_axis))) 
    # creates matrix and fills with (-1, -0.3), this values will represent the rest.
    
    for (note, duration, offset) in zip(notes, durations, offsets):
        how_many = int(float(duration)/0.25) # indicates time duration for single note.
       
        
        # Define difference between single and double note.
        # I have choose the value for first touch, the another value for contiunation
        # lets make it randomize
        first_touch = np.random.uniform(upper_second, max_value, 1)
        # continuation = np.random.randint(low=-1, high=1) * np.random.uniform(lower_second, upper_first, 1)
        continuation = np.random.uniform(lower_second, upper_first, 1)
        if ('.' not in str(note)): # it is not chord. Single note.
            our_matrix[note, int(offset * 4)] = first_touch
            our_matrix[note, int((offset * 4) + 1) : int((offset * 4) + how_many)] = continuation

        else: # For chord
            chord_notes_str = [note for note in note.split('.')] 
            chord_notes_float = list(map(int, chord_notes_str)) # take notes in chord one by one

            for chord_note_float in chord_notes_float:
                our_matrix[chord_note_float, int(offset * 4)] = first_touch
                our_matrix[chord_note_float, int((offset * 4) + 1) : int((offset * 4) + how_many)] = continuation
                
    return our_matrix



def check_float(duration): # this function fix the issue which comes from some note's duration. 
                           # For instance some note has duration like 14/3 or 7/3. 
    if ('/' in duration):
        numerator = float(duration.split('/')[0])
        denominator = float(duration.split('/')[1])
        duration = str(float(numerator/denominator))
    return duration




def midi_to_matrix(filename, length=250): # convert midi file to matrix for DL architecture.
    
    midi = music21.converter.parse(filename)
    notes_to_parse = None
    
    parts = music21.instrument.partitionByInstrument(midi)
    
    instrument_names = []
    
    try:
        for instrument in parts: # learn names of instruments
            name = (str(instrument).split(' ')[-1])[:-1]
            instrument_names.append(name)
    
    except TypeError:
        print ('Type is not iterable.')
        return None
    
    print('Instruments found: ')
    print(instrument_names)
    # just take piano part
    try:
        piano_index = instrument_names.index('Bass')
    except ValueError:
        print ('%s have not any Bass part' %(filename))
        return None
    
    
    notes_to_parse = parts.parts[piano_index].recurse()
    
    duration_piano = float(check_float((str(notes_to_parse._getDuration()).split(' ')[-1])[:-1]))

    durations = []
    notes = []
    offsets = []
    
    for element in notes_to_parse:
        if isinstance(element, note.Note): # if it is single note
            notes.append(note_to_int(str(element.pitch)))
            duration = str(element.duration)[27:-1]
            durations.append(check_float(duration))
            offsets.append(element.offset)

        elif isinstance(element, chord.Chord): # if it is chord
            notes.append('.'.join(str(note_to_int(str(n)))
                                  for n in element.pitches))
            duration = str(element.duration)[27:-1]
            durations.append(check_float(duration))
            offsets.append(element.offset)

    
    
    our_matrix = notes_to_matrix(notes, durations, offsets)
    
    try:
        freq, time = our_matrix.shape
    except AttributeError:
        print ("'tuple' object has no attribute 'shape'")
        return None
            
    if (time >= length):
        return (our_matrix[:,:length]) # We have to set all individual note matrix to same shape for Generative DL.
    else:
        print ('%s have not enough duration' %(filename))
        
        
        
        
def int_to_note(integer):
    # convert pitch value to the note which is a letter form. 
    note_base_name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave_detector = (integer // 12) 
    base_name_detector = (integer % 12) 
    note = note_base_name[base_name_detector] + str((int(octave_detector))-1)
    if ('-' in note):
      note = note_base_name[base_name_detector] + str(0)
      return note
    return note

# PAY ATTENTION. From matrix form to midi form, I have to indicate first touch, continuation and rest with unique numbers.
# I choose -1.0 for rest , 0 for continuation and 1 for first touch.

lower_bound = (lower_first + lower_second) / 2
upper_bound = (upper_first + upper_second) / 2



def converter_func(arr,first_touch = 1.0, continuation = 0.0, lower_bound = lower_bound, upper_bound = upper_bound):
    # I can write this function thanks to https://stackoverflow.com/questions/16343752/numpy-where-function-multiple-conditions
    # first touch represent start for note, continuation represent continuation for first touch, 0 represent end or rest
    np.place(arr, arr < lower_bound, -1.0)
    np.place(arr, (lower_bound <= arr) & (arr < upper_bound), 0.0)
    np.place(arr, arr >= upper_bound, 1.0)
    return arr



def how_many_repetitive_func(array, from_where=0, continuation=0.0):
    new_array = array[from_where:]
    count_repetitive = 1 
    for i in new_array:
        if (i != continuation):
            return (count_repetitive)
        else:
            count_repetitive += 1
    return (count_repetitive)



def matrix_to_midi(matrix):
    first_touch = 1.0
    continuation = 0.0
    y_axis, x_axis = matrix.shape
    output_notes = []
    offset = 0
        
    # Delete rows until the row which include 'first_touch'
    how_many_in_start_zeros = 0
    for x_axis_num in range(x_axis):
        one_time_interval = matrix[:,x_axis_num] # values in a column
        one_time_interval_norm = converter_func(one_time_interval)
        if (first_touch not in one_time_interval_norm):
            how_many_in_start_zeros += 1
        else:
            break
    
    how_many_in_end_zeros = 0
    for x_axis_num in range(x_axis-1,0,-1):
        one_time_interval = matrix[:,x_axis_num] # values in a column
        one_time_interval_norm = converter_func(one_time_interval)
        if (first_touch not in one_time_interval_norm):
            how_many_in_end_zeros += 1
        else:
            break
        
    print ('How many rows for non-start note at beginning:', how_many_in_start_zeros)
    print ('How many rows for non-start note at end:', how_many_in_end_zeros)

    matrix = matrix[:,how_many_in_start_zeros:]
    y_axis, x_axis = matrix.shape
    print (y_axis, x_axis)

    for y_axis_num in range(y_axis):
        one_freq_interval = matrix[y_axis_num,:] # bir columndaki değerler
        # freq_val = 0 # columdaki hangi rowa baktığımızı akılda tutmak için
        one_freq_interval_norm = converter_func(one_freq_interval)
        # print (one_freq_interval)
        i = 0        
        offset = 0
        while (i < len(one_freq_interval)):
            how_many_repetitive = 0
            temp_i = i
            if (one_freq_interval_norm[i] == first_touch):
                how_many_repetitive = how_many_repetitive_func(one_freq_interval_norm, from_where=i+1, continuation=continuation)
                i += how_many_repetitive 
            if (how_many_repetitive > 0):
                new_note = note.Note(int_to_note(y_axis_num),duration=duration.Duration(0.25*how_many_repetitive))
                new_note.offset = 0.25*temp_i
                new_note.storedInstrument = instrument.Bass()
                output_notes.append(new_note)
            else:
                i += 1
    return output_notes





## Test midi_to_matrix and matrix_to_midi for single file
#from pathlib import Path
#band_name = 'Nirvana'
#song_name = 'Breed'
#filename_midi = 'midiFilesFor10701/' + band_name + '/' + song_name + '.mid'
#
#my_file_single_midi = Path(filename_midi)
#
#if my_file_single_midi.is_file():
#    result = midi_to_matrix(filename_midi, 1500)
#    output_notes = matrix_to_midi(result)
#    midi_stream = stream.Stream(output_notes)
#    output_filename = song_name + 'bass.mid'
#    midi_stream.write('midi', fp=output_filename)
#else:
#    print ("%s is not in directory" % filename_midi)
#    
#plt.imshow(result);
#plt.show()
#    
    



# Build database
# Sources : https://chsasank.github.io/keras-tutorial.html
#           https://stackoverflow.com/questions/28439701/how-to-save-and-load-numpy-array-data-properly

database_npy = 'midis_array_bassTest'
my_file_database_original_npy = Path("./" + database_npy + '_original.npy')
my_file_database_binary_npy = Path("./" + database_npy + '_binary.npy')


if my_file_database_original_npy.is_file(): 
    midis_array = np.load(my_file_database_original_npy)
    
else:
    print (os.getcwd())
    root_dir = './'
    all_midi_paths = glob.glob(os.path.join(root_dir,'midiFilesForBassTest/*mid'))
    print (all_midi_paths)
    matrix_of_all_midis = []

    # All midi have to be in same shape. 
    for single_midi_path in all_midi_paths:
        print (single_midi_path)
        matrix_of_single_midi = midi_to_matrix(single_midi_path, length=1500)
        if (matrix_of_single_midi is not None):
            matrix_of_all_midis.append(matrix_of_single_midi)
            print (matrix_of_single_midi.shape)
    midis_array_original = np.asarray(matrix_of_all_midis)
    # hack to make all binary and save both orig. and binary versions
    midis_array_binary = midis_array_original.copy(); 
    midis_array_binary[midis_array_binary != 0] = 1;
    np.save(my_file_database_original_npy, midis_array_original)
    np.save(my_file_database_binary_npy, midis_array_binary)
    
    # for me so I can visualize easier...
    sp.io.savemat('./originalThing.mat', mdict={'midis_array_original': midis_array_original})
    sp.io.savemat('./binaryThing.mat',mdict={'midis_array_binary': midis_array_binary})
    
    print('Done!')