import mido
import time
import keyboard  # To detect laptop key presses
import threading  # To allow concurrent playback and recording
import logging
from threading import Event
import heapq

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

start_time = 0.00
event = Event()

def export_to_midi(recorded_notes, filename="output.mid", tempo=120, ticks_per_beat=480):
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Insert tempo event
    microseconds_per_beat = int(60_000_000 / tempo)
    track.append(mido.MetaMessage('set_tempo', tempo=microseconds_per_beat, time=0))

    # Sort notes by start_time
    notes = sorted(recorded_notes, key=lambda n: n.start_time)
    last_tick = 0

    for note in notes:
        start_tick = int(note.start_time * ticks_per_beat * tempo / 60)
        delta = start_tick - last_tick
        track.append(mido.Message('note_on', note=note.note_on_msg.note, velocity=note.note_on_msg.velocity, time=delta))
        end_tick = int(note.end_time * ticks_per_beat * tempo / 60)
        track.append(mido.Message('note_off', note=note.note_off_msg.note, velocity=note.note_off_msg.velocity, time=end_tick - start_tick))
        last_tick = end_tick

    mid.save(filename)

def import_from_midi(filename="output.mid", tempo=120, ticks_per_beat=480):
    mid = mido.MidiFile(filename)
    recorded_notes = []
    active_notes = {}
    tempo = 120  # Default, can be read from the MIDI file if needed

    for track in mid.tracks:
        elapsed_ticks = 0
        for msg in track:
            elapsed_ticks += msg.time
            if msg.type == 'set_tempo':
                tempo = mido.tempo2bpm(msg.tempo)
            elif msg.type == 'note_on' and msg.velocity > 0:
                elapsed_time = elapsed_ticks * 60 / (ticks_per_beat * tempo)
                active_notes[msg.note] = Note(mido.Message('note_on', note=msg.note, velocity=msg.velocity, time=elapsed_time))
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_notes:
                    elapsed_time = elapsed_ticks * 60 / (ticks_per_beat * tempo)
                    note = active_notes.pop(msg.note)
                    note.set_note_off(mido.Message('note_off', note=msg.note, velocity=msg.velocity, time=elapsed_time))
                    recorded_notes.append(note)
    recorded_notes.sort(key=lambda x: x.start_time)
    return recorded_notes


def n_second_print(output_string, t=1):
    if (int(time.time()) * 10) % (10 * t) == 0:
        print(f"{output_string}")

def find_input_port():
    result = None
    # List available MIDI ports
    logging.info("Available MIDI input ports:")
    for port in mido.get_input_names():
        if "CASIO" in port:
            result = port

    logging.info(f"found input port: {result}")
    return result

def find_output_port():
    result = None
    logging.info("Available MIDI output ports:")
    for port in mido.get_output_names():
        if "CASIO" in port:
            result = port

    logging.info(f"found output port: {result}")
    return result

def set_seq_start_time():
    global start_time
    start_time = time.time()
    logging.debug(f"start_time: {start_time}")

def get_seq_elapsed_time():
    logging.debug(f"start_time: {start_time}")
    logging.debug(f"get_seq_elapsed_time: {time.time() - start_time}")
    return time.time() - start_time

class Note:
    def __init__(self, note_on_msg, note_off_msg=None):
        self.note_on_msg = note_on_msg
        self.note_off_msg = note_off_msg
        self.start_time = note_on_msg.time

    def set_note_off(self, note_off_msg):
        self.note_off_msg = note_off_msg
        self.end_time = note_off_msg.time

    def __repr__(self):
        return f'Note (ON: {self.note_on_msg}, OFF: {self.note_off_msg})'

def record_midi(is_playing, recorded_notes, input_port=None):
    """Continuously records notes and adds them to the sequence."""
    logging.info("record_midi...")
    active_notes = {}

    with mido.open_input(input_port) as inport:
        while is_playing():
            for msg in inport.iter_pending():
                if not (active_notes or recorded_notes):
                    set_seq_start_time()

                msg.time = get_seq_elapsed_time()
                if msg.type == 'note_on':
                    active_notes[msg.note] = Note(msg)
                elif msg.type == 'note_off' and msg.note in active_notes:
                    note = active_notes.pop(msg.note)
                    note.set_note_off(msg)
                    recorded_notes.append(note)
                    n_second_print(f"\nRECORD MENU - Added note: {note} press q to quit recording...", 5)
                    recorded_notes.sort(key=lambda x: x.start_time)
            if keyboard.is_pressed('q'):
                logging.info("Stopped adding notes.")
                for note in recorded_notes:
                    logging.debug(note)
                return

def play_midi_smarter(is_playing, recorded_notes, output_port=None):
    """Plays recorded notes, handling overlapping notes more efficiently."""
    logging.info("play_midi_smarter...")
    with mido.open_output(output_port) as outport:
        events = []
        update_event_queue(events, recorded_notes)
        recorded_notes_size = len(recorded_notes)

        while is_playing():
            if(recorded_notes_size !=  len(recorded_notes)):
                update_event_queue(events, recorded_notes)
                recorded_notes_size = len(recorded_notes)

            set_seq_start_time()
            loop_events = list(events)  # Create a copy of the events heap
            heapq.heapify(loop_events)  # Ensure it's a valid heap
            while loop_events:
                event_time, msg, event_type = heapq.heappop(loop_events)
                logging.debug(f"event_time: {event_time})")
                sleep_time = event_time - get_seq_elapsed_time()
                logging.debug(f"sleep_time: {sleep_time})")
                event.wait(max(0, sleep_time))
                outport.send(msg)
                logging.debug(f"Played: {msg} ({event_type})")


def update_event_queue(events, recorded_notes):
    for note in recorded_notes:
        # Push note on and off events to the priority queue
        heapq.heappush(events, (note.start_time, note.note_on_msg, 'on'))
        heapq.heappush(events, (note.end_time, note.note_off_msg, 'off'))


def start_overdub_loop(recorded_notes, input_port=None, output_port=None):
    """Starts looping playback and allows overdubbing."""
    logging.info("start_loop...")
    playing = [True]  # Mutable object to control playback state

    def is_playing():
        return playing[0]

    def stop_playing():
        playing[0] = False

    # Start playback in a separate thread
    playback_thread = threading.Thread(target=play_midi_smarter, args=(is_playing, recorded_notes, output_port))
    playback_thread.start()

    logging.info("dropping in to start_loop...")

    # Allow real-time recording while playing
    record_midi(is_playing, recorded_notes, input_port)

    stop_playing()
    playback_thread.join()  # Wait for playback to finish

def start_play_loop(recorded_notes, input_port=None, output_port=None):
    """Starts looping playback and allows overdubbing."""
    logging.info("start_loop...")
    playing = [True]  # Mutable object to control playback state

    def is_playing():
        return playing[0]

    def stop_playing():
        playing[0] = False

    # Start playback in a separate thread
    playback_thread = threading.Thread(target=play_midi_smarter, args=(is_playing, recorded_notes, output_port))
    playback_thread.start()

    logging.info("dropping in to start_loop...")

    while is_playing():
        n_second_print(f"\nPLAY MENU: press q to quit playing...", 5)

        if keyboard.is_pressed('q'):
            logging.info("Stop playing notes.")
            break

    stop_playing()
    playback_thread.join()  # Wait for playback to finish

def main():
    recorded_notes = []
    input_port = find_input_port()
    output_port = find_output_port()

    while True:
        n_second_print("\nMAIN MENU: Press 'r' to record, 'p' to just play, 'o' to play & overdub, 's' to save, 'l' to load, 'x' to exit.", 5)

        if keyboard.is_pressed('r'):
            recorded_notes.clear()  # Clear previous recordings
            set_seq_start_time()
            record_midi(lambda: True, recorded_notes, input_port)

        if keyboard.is_pressed('o'):
            start_overdub_loop(recorded_notes, input_port, output_port)

        if keyboard.is_pressed('p'):
            start_play_loop(recorded_notes, input_port, output_port)

        if keyboard.is_pressed('s'):
            # Save the recorded notes as a timestamped MIDI file
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.mid"
            export_to_midi(recorded_notes, filename=filename)
            logging.info(f"Saved recording as {filename}")

        if keyboard.is_pressed('l'):
            # Load MIDI file into recorded_notes
            filename = input("Enter the filename of the MIDI file to load: ").strip()
            try:
                recorded_notes = import_from_midi(filename)
                logging.info(f"Successfully loaded MIDI file: {filename}")
            except FileNotFoundError:
                logging.error(f"File not found: {filename}")
            except Exception as e:
                logging.error(f"Failed to load MIDI file: {e}")

        if keyboard.is_pressed('x'):
            logging.info("Exiting program.")
            break

        time.sleep(0.1)  # Small delay to prevent high CPU usage

if __name__ == "__main__":
    main()
