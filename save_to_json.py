import cv2
import face_recognition
import json
import os
if not os.path.exists("date.json"):
    with open("date.json","w") as f:
        json.dump({"people":[]},f)
with open ("date.json","r")as f:
    date=json.load(f)


known_encodings=[p["encoding"] for p in date["people"]]
known_ids=[p["id"]for p in date ["people"]]
known_name=[p["name"]for p in date ["people"]]

cap = cv2.VideoCapture(0) # 0 means caputer with main camara if you use anthor put 1
while (True):
    ret, frame=cap.read() # ret return true(works) or false , frame: if the photo farm of color array
    if not ret:
        break
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) #  (from BGR TO RGB)
    face_locations=face_recognition.face_locations(rgb) # location of every face
    face_encodings=face_recognition.face_encodings(rgb,face_locations) #encoding for every face (vector reprasantfacial features )

    for face_encoding, face_location in zip(face_encodings, face_locations):
        matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.5)
        if (True in matches):
            idx=matches.index(True)
            name= known_name[idx]
            id_ = known_ids[idx]
            print("Known:", name, id_)
        else:
            print("Unknown person")
            name = input("Enter name: ")
            id_ = input("Enter ID: ")
            new_person = {
                "name": name,
                "id": id_,
                "encoding": face_encoding.tolist()
            }
            date["people"].append(new_person)
            with open("date.json","w") as f:
                json.dump(date, f, indent=4)
            known_encodings.append(face_encoding.tolist())
            known_name.append(name)
            known_ids.append(id_)

    cv2.imshow("Camera", frame)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()

