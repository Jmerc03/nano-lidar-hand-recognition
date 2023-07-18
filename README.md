## <div align="center" >Custom YOLOv8 Dectection with LiDAR Activation</div>

## <div align="left">Prerequisites</div>
Make sure you have a conda environment that can run [yolov5.](https://github.com/ultralytics/yolov5)

Common errors include:
- Not having the correct torch verison. Use the correct version for your system. I recommend using the [Pytorch website.](https://pytorch.org/)

Get [rplidar](https://github.com/Slamtec/rplidar_sdk) working on your machine. 

Common erros include:
- Not giving the port the correct permisions
```bash
ls /dev/tty*
chmod 666 /dev/ttyUSB0
```
- Not putting the baude rate on your command
```bash
./ultra_simple --channel --serial /dev/ttyUSB0 115200
```
- Sometimes it is necessary to add the user to the dialout group
```bash
sudo adduser second_user dialout
```


## <div align="left">YOLOv8 + LiDAR</div>
First make sure you have a conda environment that can run yolov5
Then run these commands.

```bash
pip install -r requirements.txt
```
The first time you run the program you will have give permision to run.sh and run it:
```bash
chmod 0666 ./run.sh 
./run.sh
```

For every other time just run:
```bash
./run.sh
```

## <div align="left">Extra Information</div>
To use segmentation with other objects or models simply replace the model best.pt with your own. This file is in ./runs/best.pt

Currently the system writes to USB1, but that port may or may not be avaliable. To change this go to line 326 in [hope.py](./segment/hope.py) and change the port.

To pass variables inbetween threads use a que. There are multple lines commented out for ques. You will need to pass the que into the thread as well. 

For development I am using the RPLidar A1M8 and a intel RealSence Camera.

## <div align="left">Future Features</div>
In the future I hope to get the screen to output after each frame, but for the sake of releasing a working version, that feature was scrapped. 