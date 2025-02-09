import mido

# Replace with the detected MIDI output port name
midi_port_name = "CASIO USB-MIDI 1"

# Open the MIDI output port to send messages
with mido.open_output(midi_port_name) as port:
    print(f"Connected to {midi_port_name}")

    # Send a middle C (MIDI note 60) with velocity 64 (moderate volume)
    note_on = mido.Message('note_on', note=60, velocity=64)
    port.send(note_on)
    print("Note On: C4 (Middle C)")

    # Keep the note playing for 2 seconds
    import time
    time.sleep(2)

    # Send a Note Off message to stop the note
    note_off = mido.Message('note_off', note=60, velocity=64)
    port.send(note_off)
    print("Note Off: C4 (Middle C)")
