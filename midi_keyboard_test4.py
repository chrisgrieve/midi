import mido
import time

# List available MIDI ports
print("Available MIDI input ports:")
for port in mido.get_input_names():
    if "CASIO" in port:
        input_port = port

print("\nAvailable MIDI output ports:")
for port in mido.get_output_names():
    if "CASIO" in port:
        output_port = port

msg_arr = []
count = 0

print(f"input_port: {input_port}")
print(f"output_port: {output_port}")

start_time = time.time()  # Capture the starting time

# Open the MIDI input port to listen for messages
with mido.open_input(input_port) as port:
    print(f"Listening for MIDI messages from {input_port}... Press keys on your keyboard.")

    # record incoming messages in real-time
    for msg in port:
        if msg.type in ['note_on', 'note_off']:
            current_time = time.time()
            elapsed_time = current_time - start_time  # Calculate time difference
            start_time = current_time  # Update start time for the next note

            # Store the message with calculated time
            msg.time = elapsed_time

            print(f"input {msg}")
            msg_arr.append(msg)
            if len(msg_arr) >= 22:
                msg_arr[0].time = 0
                print("got notes...")
                break;

time.sleep(5)
# Open the MIDI output port to send messages
with mido.open_output(output_port) as port:
    print(f"Connected to {output_port}")
    for i in range(5):
        for msg in msg_arr:
            time.sleep(msg.time)
            print(f"sending {msg}")
            port.send(msg)
        time.sleep(0.3)

        # Send a Note Off message to definitely stop the note
        # last_note = msg_arr[-1]
        # note_off = mido.Message('note_off', note=last_note.note)
        # print(f"sending {note_off}")
        # port.send(note_off)


