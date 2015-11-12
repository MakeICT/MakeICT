#define DEBUG

/*-----( Import needed libraries )-----*/
#include <SoftwareSerial.h>
#include <Wire.h>
#include <SPI.h>
#include <LiquidCrystal.h>
#include <Adafruit_NeoPixel.h>
#include <EEPROM.h>
#include <PN532_SPI.h>
#include "PN532Interface.h"

#include "ring.h"
#include "reader.h"
#include "rs485.h"
#include "lcd.h"

/*-----( Declare Constants and Pin Numbers )-----*/
//Serial protocol definitions
#define SSerialRX        6      //Serial Receive pin
#define SSerialTX        7      //Serial Transmit pin
#define SSerialTxControl 8      //RS485 Direction control

//Software SPI pins for PN532
#define PN532_SS   10

//Info for NeoPixel ring
#define PIN            2        //Pin communicating with NeoPixel Ring
#define NUMPIXELS      16       //Number of NeoPixels in Ring

/*-----( Declare objects )-----*/
Reader card_reader;

rs485 bus(SSerialRX, SSerialTX, SSerialTxControl);
Ring status_ring(PIN, NUMPIXELS);
LCD readout;

/*-----( Declare Variables )-----*/
int state;
uint8_t byteReceived;
int byteSend;
uint8_t packet[255];  //this could be made dynamic?
uint8_t packetIndex;

/*-----( Declare Functions )-----*/
uint8_t* nfc_poll();
void save_address(uint8_t addr);
uint8_t get_address();

void setup(void) {  
  readout.print(0,0, "Initializing...");
  Serial.begin(115200);
  Serial.println("setup()");
  if(!card_reader.start())  {
    readout.print(0,1,"ERROR: NFC");
    status_ring.lightSolid(40, 13, 40);
  }
  else  {
  status_ring.lightSolid(20, 13, 0);
  readout.print(0,1, "Ready!");
  }
  pinMode(3, OUTPUT);
}


void loop(void) {
  //Serial.println("loop()");
  
  //check for NFC card
  uint8_t uid[7];
  uint8_t id_length;
  if(card_reader.poll(uid, &id_length))  {
    Serial.println("1");
    if (uid[0]+uid[1]+uid[2]+uid[3] != 0)  {
      Serial.println("2");
      status_ring.lightSolid(40,30,0);  //change ring to yellow - indicate waiting state
      bus.send_packet(0x01, 0x00, F_SEND_ID, uid, 7); 
      delay(1000);
      status_ring.lightSolid(20,0,0);
    }
  }
  
  //check for data on the rs485 bus
  for (int i = bus.available(); i > 0; i--)  {
    byteReceived = bus.receive();    // Read received byte
    Serial.println(byteReceived);
    if(byteReceived == FLAG)  {
      packetIndex = 0;
      //TODO: verify packet integrity
      //TODO: check addresses
      uint8_t length = packet[0];
      uint8_t src_address = packet[1];
      uint8_t dst_address = packet[2];
      uint8_t function = packet[3];
      
      //Display packet info
      Serial.print("length: ");
      Serial.println(length);
      Serial.print("source address: ");
      Serial.println(src_address);
      Serial.print("destination address: ");
      Serial.println(dst_address);
      Serial.print("function: ");
      Serial.println(function);
      Serial.print("data: ");
      for(uint8_t i = 4; i < length; i++)  {
         Serial.print(packet[i]);
         Serial.print(',');
      }
      Serial.println(' ');
      
      //Process functions
      switch(function)
      {
        case F_UNLOCK_DOOR:
          //TODO: add non-blocking timeout
          digitalWrite(3, HIGH);
          break;
        case F_LOCK_DOOR:
          digitalWrite(3, LOW);
          break;
      }
    }
    else  {
      packet[packetIndex++] = byteReceived; 
    }   
  } 
}

void save_address(uint8_t addr)  {
  EEPROM.write(0, addr);
}

uint8_t get_address()  {
  EEPROM.read(0);
}

