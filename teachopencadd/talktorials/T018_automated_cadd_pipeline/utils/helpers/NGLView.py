# Standard library:
import time  # for creating pauses during the runtime (e.g. to wait for the response of API requests)

# 3rd-party packages:
import nglview as nv  # for visualization of the protein and protein-related data (e.g. binding sites, docking poses)
from ipywidgets import (
    AppLayout,
    Layout,
    Select,
    Button,
)  # for interactive outputs in the Jupyter Notebook
import matplotlib as mpl  # for changing the display settings of plots (see bottom of the cell: Settings)
import matplotlib.pyplot as plt  # for plotting of data
from matplotlib import (
    colors,
)  # for plotting color-maps (for visualization of protein-ligand interactions)
import numpy as np  # for some more functionalities when using Pandas (e.g. for handling NaN values)
import pandas as pd  # for creating dataframes and handling data

# Settings:
mpl.rcParams["figure.dpi"] = 300  # for plots with higher resolution
mpl.rcParams["agg.path.chunksize"] = 10000  # for handling plots with large number of data points


def protein(input_type, input_value, output_image_filename=None):
    """
    Contain all the necessary functions for visualizing protein data

    Parameters
    ----------
    input_type : str
        Either "pdb_code" or a file extension e.g. "pdb".
    input_value: str or pathlib.Path object
        Either the PDB-code of the protein, or a local filepath.
    output_image_filename : str (optional; default: None)
        Filename to save a static image of the protein.

    Returns
    -------
        NGLViewer object
        Interactive NGL viewer of the given Protein
        and (if available) its co-crystallized ligand.
    """

    if input_type == "pdb_code":
        viewer = nv.show_pdbid(input_value, height="600px")
    else:
        with open(input_value) as f:
            viewer = nv.show_file(f, ext=input_type, height="600px", default_representation=False)
            viewer.add_representation("cartoon", selection="protein")

    viewer.add_representation(repr_type="ball+stick", selection="hetero and not water")
    viewer.center("protein")

    if output_image_filename != None:
        viewer.render_image(trim=True, factor=2)
        viewer._display_image()
        viewer.download_image(output_image_filename)
    return viewer


def binding_site(protein_input_type, protein_input_value, ccp4_filepath):
    """
    3D visualization of a binding pocket using a CCP4 file.

    Parameters
    ----------
    protein_input_type : str
        Either "pdb_code" or a file extension e.g. "pdb".
    protein_input_value: str or pathlib.Path object
        Either the PDB-code of the protein, or a local filepath.
    ccp4_filepath : str
        Local file path of the output of the Binding Site Detection.

    Returns
    -------
    NGL viewer that visualizes the selected pocket at its respective position.
    """
    viewer = NGLView.protein(protein_input_type, protein_input_value)
    with open(ccp4_filepath, "rb") as f:
        viewer.add_component(f, ext="ccp4")
    viewer.center()

    return viewer


def docking(
    protein_filepath,
    protein_file_extension,
    list_docking_poses_filepaths,
    docking_poses_file_extension,
    list_docking_poses_labels,
    list_docking_poses_affinities,
):
    """
    Visualize a list of docking poses
    in the protein structure, using NGLView.

    Parameters
    ----------
    protein_filepath : str or pathlib.Path object
        Filepath of the extracted protein structure used in docking experiment.
    protein_file_extension : str
        File extension of the protein file, e.g. "pdb", "pdbqt" etc.
    list_docking_poses_filepaths : list of strings/pathlib.Path objects
        List of filepaths for the separated docking poses.
    docking_poses_file_extension : str
        File extension of the docking-pose files, e.g. "pdb", "pdbqt" etc.
    list_docking_poses_labels : list of strings
        List of labels for docking poses to be used for the selection menu.
    list_docking_poses_affinities : list of strings/numbers
        List of binding affinities in kcal/mol, to be viewed for each docking pose.

    Returns
    -------
        NGLView viewer
        Interactive viewer containing the protein structure and all docking poses,
        with menu to select between docking poses.
    """

    # JavaScript code needed to update residues around the ligand
    # because this part is not exposed in the Python widget
    # Based on: http://nglviewer.org/ngl/api/manual/snippets.html
    _RESIDUES_AROUND = """
    var protein = this.stage.compList[0];
    var ligand_center = this.stage.compList[{index}].structure.atomCenter();
    var around = protein.structure.getAtomSetWithinPoint(ligand_center, {radius});
    var around_complete = protein.structure.getAtomSetWithinGroup(around);
    var last_repr = protein.reprList[protein.reprList.length-1];
    protein.removeRepresentation(last_repr);
    protein.addRepresentation("licorice", {{sele: around_complete.toSeleString()}});
    """
    print("Docking modes")
    print("(CID - mode)")
    # Create viewer widget
    viewer = nv.NGLWidget(height="860px")
    viewer.add_component(protein_filepath, ext=protein_file_extension)
    # viewer.add_representation("cartoon", selection="protein")
    # Select first atom in molecule (@0) so it holds the affinity label
    label_kwargs = dict(
        labelType="text",
        sele="@0",
        showBackground=True,
        backgroundColor="black",
    )
    list_docking_poses_affinities = list(
        map(lambda x: str(x) + " kcal/mol", list_docking_poses_affinities)
    )
    for docking_pose_filepath, ligand_label in zip(
        list_docking_poses_filepaths, list_docking_poses_affinities
    ):
        ngl_ligand = viewer.add_component(docking_pose_filepath, ext=docking_poses_file_extension)
        ngl_ligand.add_label(labelText=[str(ligand_label)], **label_kwargs)

    # Create selection widget
    #   Options is a list of (text, value) tuples. When we click on select, the value will be passed
    #   to the callable registered in `.observe(...)`
    selector = Select(
        options=[(label, i) for (i, label) in enumerate(list_docking_poses_labels, 1)],
        description="",
        rows=len(list_docking_poses_filepaths) if len(list_docking_poses_filepaths) <= 52 else 52,
        layout=Layout(flex="flex-grow", width="auto"),
    )

    # Arrange GUI elements
    # The selection box will be on the left, the viewer will occupy the rest of the window
    display(AppLayout(left_sidebar=selector, center=viewer, pane_widths=[1, 6, 1]))

    # This is the event handler - action taken when the user clicks on the selection box
    # We need to define it here so it can "see" the viewer variable
    def _on_selection_change(change):
        # Update only if the user clicked on a different entry
        if change["name"] == "value" and (change["new"] != change["old"]):
            viewer.hide(
                list(range(1, len(list_docking_poses_filepaths) + 1))
            )  # Hide all ligands (components 1-n)
            component = getattr(viewer, f"component_{change['new']}")
            component.show()  # Display the selected one
            component.center(500)  # Zoom view
            # Call the JS code to show sidechains around ligand
            viewer._execute_js_code(_RESIDUES_AROUND.format(index=change["new"], radius=6))

    # Register event handler
    selector.observe(_on_selection_change)
    # Trigger event manually to focus on the first solution
    _on_selection_change({"name": "value", "new": 1, "old": None})
    return viewer


def interactions(
    protein_filepath,
    protein_file_extension,
    list_docking_poses_filepaths,
    docking_poses_file_extension,
    list_docking_poses_labels,
    list_docking_poses_affinities,
    list_docking_poses_plip_dicts,
):

    color_map = {
        "hydrophobic": [0.90, 0.10, 0.29],
        "hbond": [0.26, 0.83, 0.96],
        "waterbridge": [1.00, 0.88, 0.10],
        "saltbridge": [0.67, 1.00, 0.76],
        "pistacking": [0.75, 0.94, 0.27],
        "pication": [0.27, 0.60, 0.56],
        "halogen": [0.94, 0.20, 0.90],
        "metal": [0.90, 0.75, 1.00],
    }

    # Create selection widget
    # Options is a list of (text, value) tuples.
    # When we click on select, the value will be passed
    # to the callable registered in `.observe(...)`
    selector = Select(
        options=[(label, i) for (i, label) in enumerate(list_docking_poses_labels, 1)],
        description="",
        rows=len(list_docking_poses_filepaths) if len(list_docking_poses_filepaths) <= 52 else 52,
        layout=Layout(flex="flex-grow", width="auto"),
    )

    # Arrange GUI elements
    # The selection box will be on the left,
    # the viewer will occupy the rest of the window (but it will be added later)
    app = AppLayout(
        left_sidebar=selector,
        center=None,
        pane_widths=[1, 6, 1],
        height="860px",
    )

    # Show color-map
    fig, axs = plt.subplots(nrows=2, ncols=4, figsize=(12, 1))
    plt.subplots_adjust(hspace=1)
    fig.suptitle("Color-map of interactions", size=10, y=1.3)
    for ax, (interaction, color) in zip(fig.axes, color_map.items()):
        ax.imshow(np.zeros((1, 5)), cmap=colors.ListedColormap(color_map[interaction]))
        ax.set_title(interaction, loc="center", fontsize=10)
        ax.set_axis_off()
    plt.show()

    list_docking_poses_affinities = list(
        map(lambda x: str(x) + " kcal/mol", list_docking_poses_affinities)
    )

    # This is the event handler - action taken when the user clicks on the selection box
    # We need to define it here so it can "see" the viewer variable
    def _on_selection_change(change):
        # Update only if the user clicked on a different entry
        if change["name"] == "value" and (change["new"] != change["old"]):
            if app.center is not None:
                app.center.close()

            # NGL Viewer
            app.center = viewer = nv.NGLWidget(height="860px", default=True, gui=True)
            prot_component = viewer.add_component(
                protein_filepath, ext=protein_file_extension, default_representation=False
            )  # add protein
            prot_component.add_representation("cartoon")
            time.sleep(1)

            label_kwargs = dict(
                labelType="text",
                sele="@0",
                showBackground=True,
                backgroundColor="black",
            )
            lig_component = viewer.add_component(
                list_docking_poses_filepaths[change["new"]], ext=docking_poses_file_extension
            )  # add selected ligand
            lig_component.add_label(
                labelText=[str(list_docking_poses_affinities[change["new"]])], **label_kwargs
            )
            time.sleep(1)
            lig_component.center(duration=500)

            # Add interactions
            interactions = list_docking_poses_plip_dicts[change["new"]]

            interacting_residues = []

            for interaction_type, interaction_list in interactions.items():
                color = color_map[interaction_type]
                if len(interaction_list) == 1:
                    continue
                df_interactions = pd.DataFrame.from_records(
                    interaction_list[1:], columns=interaction_list[0]
                )
                for _, interaction in df_interactions.iterrows():
                    name = interaction_type
                    viewer.shape.add_cylinder(
                        interaction["LIGCOO"],
                        interaction["PROTCOO"],
                        color,
                        [0.1],
                        name,
                    )
                    interacting_residues.append(interaction["RESNR"])
            # Display interacting residues
            res_sele = " or ".join([f"({r} and not _H)" for r in interacting_residues])
            res_sele_nc = " or ".join(
                [f"({r} and ((_O) or (_N) or (_S)))" for r in interacting_residues]
            )

            prot_component.add_ball_and_stick(
                sele=res_sele, colorScheme="chainindex", aspectRatio=1.5
            )
            prot_component.add_ball_and_stick(
                sele=res_sele_nc, colorScheme="element", aspectRatio=1.5
            )

    # Register event handler
    selector.observe(_on_selection_change)
    # Trigger event manually to focus on the first solution
    _on_selection_change({"name": "value", "new": 0, "old": None})
    return app
