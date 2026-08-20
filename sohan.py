print("Sohan is online.")
print("Hello! I am Sohan, your personal AI assistant.")
import speech_recognition as sr
import pyttsx3

recognizer = sr.Recognizer()
voice = pyttsx3.init()

voice.say("Sohan is online.")
voice.runAndWait()

while True:
    try:
        with sr.Microphone() as source:
            print("\nListening...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source)

        command = recognizer.recognize_google(audio)

        print("You:", command)

        if "sohan" in command.lower():
            voice.say("Yes, I am listening.")
            voice.runAndWait()

        if "exit" in command.lower() or "shutdown sohan" in command.lower():
            voice.say("Goodbye.")
            voice.runAndWait()
            break

    except sr.UnknownValueError:
        print("I didn't understand that.")

    except Exception as error:
        print("Error:", error)