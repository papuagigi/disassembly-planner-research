# Portable native replay

This is saved MuJoCo event replay,not a live physical solver or robot controller. All final episodes,including failures/native-warning outcomes,are retained. Raw and warning-free goals are separate. Reference sequences are derived after evaluation from actual successful warning-free episodes;they are not unique optimal answers.

From this directory run `python3 -m http.server 8783 --bind 127.0.0.1`,then open http://127.0.0.1:8783/viewer/index.html . The viewer uses browser gzip decompression. Source CAD archives,native libraries,credentials and model CLI logs are not included.

Selected visual meshes are normalized derivatives of the official ASAP dataset,not CAD designed by this project. Original rights remain with the respective sources. Upstream repository:https://github.com/yunshengtian/ASAP ;dataset:https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/test_assembly.zip . The upstream software MIT notice is included when available;this project does not grant a new license over third-party CAD. Three.js notices remain in viewer/vendor/LICENSE.
