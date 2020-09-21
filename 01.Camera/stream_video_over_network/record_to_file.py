import picamera

camera = picamera.PiCamera()
camera.resolution = (800,600)
camera.framerate = 60
camera.color_effects = (128,128)
camera.start_recording('my_video_60s.h264')
camera.wait_recording(60)
camera.stop_recording()