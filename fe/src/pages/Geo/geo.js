import React, { useState, useEffect } from "react";
import { Map, Marker } from "pigeon-maps";
import { withStyles } from "@material-ui/core/styles";
import useGeolocation from "./useGeolocation";

const styles = theme => ({
  root: {
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "space-around",
    overflow: "hidden",
    backgroundColor: theme.palette.background.paper,
    marginTop: '100px'
  },
  gridList: {
    width: 500,
    height: 450
  },
  subheader: {
    width: "100%"
  }
});

function GeoLocation(props) {
  const { loading, error, data } = useGeolocation();
  const [lat, setLat] = useState(null);
  const [lng, setLng] = useState(null);
  const [hea, setHea] = useState(null);
  const [spd, setSpd] = useState(null);

  useEffect(() => {
    let watchId;
    if (navigator.geolocation) {
      watchId = navigator.geolocation.watchPosition((position) => {
        const { latitude, longitude, heading, speed } = position.coords;
        setLat(latitude);
        setLng(longitude);
        setHea(heading);
        setSpd(speed);

        // Send location data to the backend
        fetch("http://localhost:5000/set-location", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            user_id: "user123", // Replace with actual user ID
            latitude: latitude,
            longitude: longitude,
            heading: heading,
            speed: speed
          })
        }).then(response => response.json())
          .then(data => console.log(data))
          .catch(error => console.error('Error:', error));
      }, (e) => {
        console.log(e);
      });
    } else {
      console.log('GeoLocation not supported by your browser!');
    }

    return () => {
      if (watchId) {
        navigator.geolocation.clearWatch(watchId);
      }
    };
  }, []);

  return (
    <div style={{ backgroundColor: 'white', padding: 72 }}>
      <h1>Coordinates</h1>
      {lat !== null && <p>Latitude: {lat}</p>}
      {lng !== null && <p>Longitude: {lng}</p>}
      {hea !== null && <p>Heading: {hea}</p>}
      {spd !== null && <p>Speed: {spd}</p>}
      <h1>Map</h1>
      {lat && lng && (
        <Map height={300} defaultCenter={[lat, lng]} defaultZoom={15} center={[lat, lng]}>
          <Marker width={50} anchor={[lat, lng]} />
        </Map>
      )}
    </div>
  );
}

export default withStyles(styles)(GeoLocation);
