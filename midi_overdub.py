import mido
import time
import keyboard  # To detect laptop key presses
import threading  # To allow concurrent playback and recording
from threading import Event

start_time = 0.00
event = Event()

def n_second_print(output_string, t=1):
    if (int(time.time()) * 10) % (10*t) == 0: 
        print(f"{output_string}")

def find_input_port():
    result = None
    # List available MIDI ports
    print("Available MIDI input ports:")
    for port in mido.get_input_names():
        if "CASIO" in port:
            result = port

    print(f"found input port: {result}")
    return result

def find_output_port():
    result = None
    print("Available MIDI output ports:")
    for port in mido.get_output_names():
        if "CASIO" in port:
            result = port

    print(f"found output port: {result}")
    return result

def set_seq_start_time():
    global start_time
    start_time = time.time()
    print(f"start_time: {start_time}")

def get_seq_elapsed_time():
    print(f"start_time: {start_time}")
    print(f"get_seq_note_time: {time.time() - start_time}")
    return time.time() - start_time

class Note:
    def __init__(self, note_on_msg, note_off_msg=None):
        self.note_on_msg = note_on_msg
        self.note_off_msg = note_off_msg
        self.start_time = note_on_msg.time
        self.end_time = note_off_msg.time if note_off_msg else None

    def set_note_off(self, note_off_msg):
        self.note_off_msg = note_off_msg
        self.end_time = note_off_msg.time

    def __repr__(self):
        return f'Note (ON: {self.note_on_msg}, OFF: {self.note_off_msg})'





def record_midi(is_playing, recorded_notes, input_port=None):
    """Continuously records notes and adds them to the sequence."""
    print("record_midi...")
    inport = mido.open_input(input_port) if input_port else mido.open_input()
    active_notes = {}

    while is_playing():
        for msg in inport.iter_pending():
            if msg.type == 'note_on':
                active_notes[msg.note] = Note(msg)
            elif msg.type == 'note_off' and msg.note in active_notes:
                note = active_notes.pop(msg.note)
                note.set_note_off(msg)
                recorded_notes.append(note)
                print(f"Added note: {note} press q to quit recording...")
                recorded_notes.sort(key=lambda x: x.start_time)
        if keyboard.is_pressed('q'):
            print("Stopped adding notes.")
            for note in recorded_notes:
                print(note)
            return
            
def play_midi(is_playing, recorded_notes, output_port=None):
    """Plays recorded notes in a loop."""
    print("play_midi...")
    with mido.open_output(output_port) as outport:
        while is_playing():
            set_seq_start_time()
            for note in recorded_notes:
                sleep_time = note.start_time - get_seq_elapsed_time()
                event.wait(max(0, sleep_time))
                print(f"done sleep")
                outport.send(note.note_on_msg)
                print(f"Played: {note.note_on_msg} Press 's' to stop and (if overdub) 'q' to add more notes")
                sleep_time = note.end_time - get_seq_elapsed_time()
                event.wait(max(0, sleep_time))
                outport.send(note.note_off_msg)
                print(f"Played: {note.note_off_msg} Press 's' to stop and (if overdub) 'q' to add more notes")



def start_overdub_loop(recorded_notes, input_port=None, output_port=None):
    """Starts looping playback and allows overdubbing."""
    print("start_loop...")
    playing = [True]  # Mutable object to control playback state

    def is_playing():
        return playing[0]

    def stop_playing():
        playing[0] = False

    # Start playback in a separate thread
    playback_thread = threading.Thread(target=play_midi, args=(is_playing, recorded_notes, output_port))
    playback_thread.start()

    print("dropping in to start_loop...")

    # Allow real-time recording while playing
    record_midi(is_playing, recorded_notes, input_port)

    stop_playing()
    playback_thread.join()  # Wait for playback to finish

def start_play_loop(recorded_notes, input_port=None, output_port=None):
    """Starts looping playback and allows overdubbing."""
    print("start_loop...")
    playing = [True]  # Mutable object to control playback state

    def is_playing():
        return playing[0]

    def stop_playing():
        playing[0] = False

    # Start playback in a separate thread
    playback_thread = threading.Thread(target=play_midi, args=(is_playing, recorded_notes, output_port))
    playback_thread.start()

    print("dropping in to start_loop...")

    while is_playing():
        n_second_print(f"press q to quit playing...", 5)

        if keyboard.is_pressed('q'):
            print("Stop playing notes.")
            break;

    stop_playing()
    playback_thread.join()  # Wait for playback to finish

def main():
    recorded_notes = []
    input_port = find_input_port()
    output_port = find_output_port()

    while True:
        n_second_print("\nPress 'r' to record, 'p' to just play, 'o' to play & overdub, 'x' to exit.", 5)

        if keyboard.is_pressed('r'):
            recorded_notes.clear()  # Clear previous recordings
            set_seq_start_time()
            record_midi(lambda: True, recorded_notes, input_port)

        if keyboard.is_pressed('o'):
            start_overdub_loop(recorded_notes, input_port, output_port)

        if keyboard.is_pressed('p'):
            start_play_loop(recorded_notes, input_port, output_port)

        if keyboard.is_pressed('x'):
            print("Exiting program.")
            break

        time.sleep(0.1)  # Small delay to prevent high CPU usage

if __name__ == "__main__":
    main()
