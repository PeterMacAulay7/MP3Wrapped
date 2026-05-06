# MP3Wrapped
This year I stopped streaming music, and switched to using an MP3 player. I did this for quite a few reasons but I didn't like the morals a certain companies, and I found the limitlessness of streaming to be a bit diminutive to my music listening experience. One thing I did like is the Wrapped, So I created my own for MP3 players running Rockbox

# Setup
- Download the 'MP3Wrapped.zip' folder from github, then unzip the folder
- go to https://musicbrainz.org/register and make an account, from there you can generate an api key
- then go to https://developer.spotify.com/documentation/web-api to get a 'CLIENT_ID' and 'CLIENT_SECRET'
- Open the 'config.json' file in the root of the MP3Wrapped folder and edit the evironment variable for with the keys you just got
  - I went with two databases because I found music brainz would sometimes fail, and while I'm no spotify fan, having their database as a backup leads to albums being identified with no problems. Think of it as taking from their database.
- Depending on where your actual music files are located, either edit the path for 'music' in the 'config.json' file, or put all your music into the music folder in the root of the MP3Wrapped folder.
- Double click the MP3Wrapped.bat file and you should be all done.
- The first time you run the program it will likely take a long time because it has to catalogue all your music, but subsequent times will run far, far faster. It skips the processing entirely, only double checking if new albums have been added.
- When the program has finished running it will automatically open the newly generated wrapped.html file

# Note
- This project is still in development, so please let me know if there is anything wrong. I know that there are things to improve, but it's just me working on this so I definitely missed things

# Example Wrapped
![[Screenshot 2026-05-06 131522.png]]![[Screenshot 2026-05-06 131531.png]]![[Screenshot 2026-05-06 131538.png]]![[Screenshot 2026-05-06 131538.png]]![[Screenshot 2026-05-06 131552.png]]![[Screenshot 2026-05-06 131618.png]]![[Screenshot 2026-05-06 131837.png]]![[Screenshot 2026-05-06 131912.png]]