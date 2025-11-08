import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QInputDialog, QMessageBox, QVBoxLayout,
                             QFileDialog, QGraphicsScene, QGraphicsView)
from PyQt6.QtCore import Qt, QPointF, QObject
from PyQt6.QtGui import QColor, QPainter, QBrush

from ui.editor_ui import EditorWindowUI
from graphical import (Controller, BlockFrame, PortItem, InstanceItem, WireItem, 
                       JunctionItem)
from data import NetlistProject
from version_manager import VersionManager


class Editor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file_path = None

        # Initialize circuit object model
        self.netlist_project = NetlistProject("circuit_project")
        self._create_default_blocks()

        self.ui = EditorWindowUI()
        self.ui.show()

        # Initialize graphical components
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QBrush(QColor("#000000")))

        self.view = QGraphicsView(self.scene)
        try:
            self.view.setRenderHints(QPainter.RenderHint.Antialiasing)
        except Exception:
            pass

        self.controller = Controller(self.scene)

        # Add the graphics view to the UI layout
        graphics_widget = self.ui.graphics_frame
        layout = graphics_widget.layout()
        if layout is None:
            layout = QVBoxLayout(graphics_widget)
        layout.addWidget(self.view)

        # Initialize version manager
        self.version_manager = VersionManager(os.path.dirname(__file__) if __file__ else ".", self.controller)

        # Mode management
        self.active_mode = None
        self.current_filter = None
        self._current_block_id = None
        
        # Initialize default blocks
        self.controller.add_block("BlockA")
        self.controller.add_block("BlockB")
        
        self.setup_menu_bar()
        self.setup_connections()
        self.refresh_objects_list()
        
        if self.ui.objects_list.count() > 0:
            self.ui.objects_list.setCurrentRow(0)
            self._show_block_by_index(0)

    def _create_default_blocks(self):
        """Create default blocks in the object model."""
        self.netlist_project.add_block("BlockA")
        self.netlist_project.add_block("BlockB")

    def setup_menu_bar(self):
        """Create the menu bar with File menu."""
        self.ui.menu_actions['open'].triggered.connect(self.open_file)
        self.ui.menu_actions['save'].triggered.connect(self.save_file)
        self.ui.menu_actions['save_as'].triggered.connect(self.save_file_as)

    def open_file(self):
        """Open a file dialog to select a scene file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Scene File",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.current_file_path = file_path
            try:
                self.controller.load_scene(file_path)
                self.refresh_objects_list()
                self.setWindowTitle(f"Editor - {file_path}")

                self.version_manager = VersionManager(
                    os.path.dirname(file_path),
                    self.controller
                )

                QMessageBox.information(self, "Success", f"Loaded: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")

    def save_file(self):
        """Save the current scene to the current file path."""
        if self.current_file_path is None:
            self.save_file_as()
        else:
            try:
                self.controller.save_scene(self.current_file_path)
                if self.version_manager:
                    self.version_manager.save_state(f"Save file: {os.path.basename(self.current_file_path)}")
                QMessageBox.information(self, "Success", f"Saved: {self.current_file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

    def save_file_as(self):
        """Save the current scene to a new file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scene File",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.current_file_path = file_path
            try:
                self.controller.save_scene(file_path)

                self.version_manager = VersionManager(
                    os.path.dirname(file_path),
                    self.controller
                )

                if self.version_manager:
                    self.version_manager.save_state(f"Save file: {os.path.basename(file_path)}")
                self.setWindowTitle(f"Editor - {file_path}")
                QMessageBox.information(self, "Success", f"Saved: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

    def setup_connections(self):
        """Connect all buttons to their handler functions."""
        # Block operations
        self.ui.add_block.clicked.connect(self.add_block)
        self.ui.del_block.clicked.connect(self.delete_block)
        self.ui.copy_block.clicked.connect(self.copy_block)
        self.ui.rename_block.clicked.connect(self.rename_block)

        # Instance operations
        self.ui.add_instance.clicked.connect(self.add_instance)
        self.ui.del_instance.clicked.connect(self.delete_instance)
        self.ui.copy_instance.clicked.connect(self.copy_instance)
        self.ui.rename_instance.clicked.connect(self.rename_instance)

        # Pin operations
        self.ui.add_pin.clicked.connect(self.add_pin)
        self.ui.del_pin.clicked.connect(self.delete_pin)
        self.ui.rename_pin.clicked.connect(self.rename_pin)

        # Net operations
        self.ui.add_net.clicked.connect(self.add_net)
        self.ui.del_net.clicked.connect(self.delete_net)
        self.ui.rename_net.clicked.connect(self.rename_net)

        # Junction operations
        self.ui.add_junction.clicked.connect(self.add_junction)
        self.ui.del_junction.clicked.connect(self.delete_junction)

        # Undo/Redo operations
        self.ui.btn_undo.clicked.connect(self.undo)
        self.ui.btn_redo.clicked.connect(self.redo)

        # Objects list selection
        self.ui.objects_list.itemClicked.connect(self.on_object_selected)

    def _get_block_id_by_index(self, idx: int):
        """Get block ID from block name at index in objects_list."""
        if idx < 0 or idx >= self.ui.objects_list.count():
            return None
        item = self.ui.objects_list.item(idx)
        block_name = item.text()
        for block_id, block_frame in self.controller.blocks.items():
            if block_frame.model.name == block_name:
                return block_id
        return None

    def _show_block_by_index(self, idx: int):
        """Show block by index."""
        bid = self._get_block_id_by_index(idx)
        if bid is None:
            return
        self.controller.show_only_block(bid)
        self._current_block_id = bid

    def _deactivate_mode(self):
        """Deactivate current mode."""
        if self.current_filter:
            try:
                self.view.viewport().removeEventFilter(self.current_filter)
            except Exception:
                pass
            self.current_filter = None

        if self.active_mode == 'wire':
            self.controller.set_add_wire_mode(False)
        elif self.active_mode == 'junction':
            self.controller.set_add_junction_mode(False)

        self.active_mode = None

    def refresh_objects_list(self):
        """Refresh the list of objects (blocks) in the objects_list widget."""
        current_selection = self.ui.objects_list.currentItem()
        current_name = current_selection.text() if current_selection else None

        self.ui.objects_list.clear()
        for block_frame in self.controller.blocks.values():
            self.ui.objects_list.addItem(block_frame.model.name)

        # Restore selection if possible
        if current_name:
            for i in range(self.ui.objects_list.count()):
                if self.ui.objects_list.item(i).text() == current_name:
                    self.ui.objects_list.setCurrentRow(i)
                    break

    def on_object_selected(self, item):
        """Handle selection of an object in the objects list."""
        block_name = item.text()
        for block_id, block_frame in self.controller.blocks.items():
            if block_frame.model.name == block_name:
                self.controller.show_only_block(block_id)
                self._current_block_id = block_id
                break

    def add_block(self):
        """Add a new block to both graphical and object model."""
        self._deactivate_mode()
        name, ok = QInputDialog.getText(self, "New block", "Block name:",
                                        text=f"Block{len(self.controller.blocks) + 1}")
        if not ok or not name:
            return

        # Check for unique name
        if self._block_name_exists(name):
            QMessageBox.warning(self, "Error", f"Block name '{name}' already exists.")
            return

        bf = self.controller.add_block(name)
        # Sync with object model
        for bf_item in self.controller.blocks.values():
            if bf_item.model.name not in self.netlist_project.blocks:
                try:
                    self.netlist_project.add_block(bf_item.model.name)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to add block to model: {e}")
        self.refresh_objects_list()
        for i in range(self.ui.objects_list.count()):
            if self.ui.objects_list.item(i).text() == bf.model.name:
                self.ui.objects_list.setCurrentRow(i)
                self._show_block_by_index(i)
                break

        if self.version_manager:
            self.version_manager.save_state(f"Add block: {name}")

    def delete_block(self):
        """Delete the selected block from both models."""
        selected = list(self.scene.selectedItems())
        blocks = [it for it in selected if isinstance(it, BlockFrame)]
        if not blocks:
            QMessageBox.information(self, "Delete Block", "Select a block to delete.")
            return
        for b in blocks:
            # Remove from object model
            if b.model.name in self.netlist_project.blocks:
                try:
                    self.netlist_project.remove_block(b.model.name)
                    if self.version_manager:
                        self.version_manager.save_state(f"Delete block: {b.model.name}")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to delete block from model: {e}")
            self.controller.delete_block(b)
        self.refresh_objects_list()

    def copy_block(self):
        """Copy the selected block with a new name."""
        selected = list(self.scene.selectedItems())
        blocks = [it for it in selected if isinstance(it, BlockFrame)]
        if not blocks:
            QMessageBox.information(self, "Copy Block", "Select a block to copy.")
            return

        block = blocks[0]
        new_name, ok = QInputDialog.getText(
            self, "Copy Block", "New block name:",
            text=f"{block.model.name}_copy"
        )
        if not ok or not new_name:
            return

        # Check for unique name
        if self._block_name_exists(new_name):
            QMessageBox.warning(self, "Error", f"Block name '{new_name}' already exists.")
            return

        try:
            # Use controller's copy method which uses model.copy() for deep copy with new IDs
            new_bf = self.controller.copy_block(block)
            new_bf.model.name = new_name
            new_bf.title.setText(new_name)
            
            # Sync with object model
            for bf_item in self.controller.blocks.values():
                if bf_item.model.name not in self.netlist_project.blocks:
                    try:
                        self.netlist_project.add_block(bf_item.model.name)
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to add block to model: {e}")
            
            self.refresh_objects_list()
            for i in range(self.ui.objects_list.count()):
                if self.ui.objects_list.item(i).text() == new_name:
                    self.ui.objects_list.setCurrentRow(i)
                    self._show_block_by_index(i)
                    break
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to copy block: {e}")

        if self.version_manager:
            self.version_manager.save_state(f"Copy block: {block.model.name} -> {new_name}")

    def rename_block(self):
        """Rename the selected block in both models."""
        selected = list(self.scene.selectedItems())
        blocks = [it for it in selected if isinstance(it, BlockFrame)]
        if not blocks:
            QMessageBox.information(self, "Rename Block", "Select a block to rename.")
            return
        block = blocks[0]
        new_name, ok = QInputDialog.getText(
            self, "Rename Block", "New name:", text=block.model.name
        )
        if ok and new_name:
            # Check for unique name (excluding current block)
            if self._block_name_exists(new_name, exclude_id=block.model.id):
                QMessageBox.warning(self, "Error", f"Block name '{new_name}' already exists.")
                return
            
            try:
                # Update object model
                if block.model.name in self.netlist_project.blocks:
                    self.netlist_project.rename_block(block.model.name, new_name)
                # Update graphical model
                block.model.name = new_name
                block.title.setText(new_name)
                self.refresh_objects_list()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to rename block: {e}")

        if self.version_manager:
            self.version_manager.save_state(f"Rename block: {block.model.name} -> {new_name}")

    def add_instance(self):
        """Add a new instance to the current block."""
        self._deactivate_mode()
        if len(self.controller.blocks) < 2:
            QMessageBox.information(self, "Info", "Need at least two blocks.")
            return
        names = [bf.model.name for bf in self.controller.blocks.values()]
        child_name, ok = QInputDialog.getItem(self, "Choose block to insert",
                                              "Block:", names, 0, False)
        if not ok:
            return
        parent_name, ok = QInputDialog.getItem(self, "Choose parent block",
                                               "Parent:", names, 0, False)
        if not ok:
            return
        if child_name == parent_name:
            QMessageBox.warning(self, "Error", "Cannot insert block into itself.")
            return
        child_frame = next(bf for bf in self.controller.blocks.values() if
                           bf.model.name == child_name)
        parent_frame = next(bf for bf in self.controller.blocks.values() if
                            bf.model.name == parent_name)
        QMessageBox.information(self, "Place",
                                "Click inside parent block to place instance.")

        def handler(ev):
            pos = self.view.mapToScene(ev.position().toPoint())
            if parent_frame.mapRectToScene(parent_frame.rect()).contains(pos):
                local = parent_frame.mapFromScene(pos)
                parent_frame.add_instance(child_frame.model, local)
                # Add to object model
                try:
                    self.netlist_project.add_instance_to_block(
                        parent_name, 
                        parent_frame.model.instances[-1].name,
                        child_name
                    )
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to add instance to model: {e}")
                self.refresh_objects_list()
                self.view.viewport().removeEventFilter(filter_obj)
                return True
            return False

        class OneShot(QObject):
            def eventFilter(self, obj, ev):
                if ev.type() == 2:
                    return handler(ev)
                return False

        filter_obj = OneShot()
        self.view.viewport().installEventFilter(filter_obj)

        if self.version_manager:
            self.version_manager.save_state(f"Add instance: {child_name} to {parent_name}")

    def delete_instance(self):
        """Delete the selected instance."""
        selected = list(self.scene.selectedItems())
        instances = [it for it in selected if isinstance(it, InstanceItem)]
        if not instances:
            QMessageBox.information(
                self, "Delete Instance", "Select an instance to delete."
            )
            return
        for inst in instances:
            # Remove from object model if applicable
            parent_block = inst.parentItem()
            if isinstance(parent_block, BlockFrame):
                block_name = parent_block.model.name
                if block_name in self.netlist_project.blocks:
                    try:
                        self.netlist_project.remove_instance_from_block(
                            block_name, inst.model.name
                        )
                        if self.version_manager:
                            self.version_manager.save_state(f"Delete instance: {inst.model.name}")
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to delete instance: {e}")
            self.controller.delete_instance(inst)

    def copy_instance(self):
        """Copy the selected instance with a new name."""
        selected = list(self.scene.selectedItems())
        instances = [it for it in selected if isinstance(it, InstanceItem)]
        if not instances:
            QMessageBox.information(self, "Copy Instance", "Select an instance to copy.")
            return
        
        inst = instances[0]
        parent_block = inst.parentItem()
        
        if not isinstance(parent_block, BlockFrame):
            QMessageBox.warning(self, "Error", "Instance parent is not a BlockFrame.")
            return
        
        new_name, ok = QInputDialog.getText(
            self, "Copy Instance", "New instance name:",
            text=f"{inst.model.name}_copy"
        )
        if not ok or not new_name:
            return
        
        # Check for unique name within parent block
        if self._instance_name_exists_in_block(parent_block, new_name):
            QMessageBox.warning(self, "Error", f"Instance name '{new_name}' already exists in this block.")
            return
        
        try:
            # Use controller's copy method which uses model.copy() for deep copy with new IDs
            new_inst_item = self.controller.copy_instance(inst, parent_block)
            new_inst_item.model.name = new_name
            new_inst_item.title.setText(new_name)
            
            # Copy to object model
            block_name = parent_block.model.name
            if block_name in self.netlist_project.blocks:
                try:
                    self.netlist_project.add_instance_to_block(
                        block_name,
                        new_name,
                        inst.model.block_name
                    )
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to add instance to model: {e}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to copy instance: {e}")

        if self.version_manager:
            self.version_manager.save_state(f"Copy instance: {inst.model.name} -> {new_name}")

    def rename_instance(self):
        """Rename the selected instance in both models."""
        selected = list(self.scene.selectedItems())
        instances = [it for it in selected if isinstance(it, InstanceItem)]
        if not instances:
            QMessageBox.information(
                self, "Rename Instance", "Select an instance to rename."
            )
            return
        inst = instances[0]
        new_name, ok = QInputDialog.getText(
            self, "Rename Instance", "New name:", text=inst.model.name
        )
        if ok and new_name:
            # Get parent block
            parent_block = inst.parentItem()
            if not isinstance(parent_block, BlockFrame):
                QMessageBox.warning(self, "Error", "Instance parent is not a BlockFrame.")
                return
            
            # Check for unique name within parent block (excluding current instance)
            if self._instance_name_exists_in_block(parent_block, new_name, exclude_id=inst.model.id):
                QMessageBox.warning(self, "Error", f"Instance name '{new_name}' already exists in this block.")
                return
            
            try:
                # Update object model
                block_name = parent_block.model.name
                old_name = inst.model.name
                if block_name in self.netlist_project.blocks:
                    self.netlist_project.rename_instance_in_block(
                        block_name, old_name, new_name
                    )
                # Update graphical model
                inst.model.name = new_name
                inst.title.setText(new_name)

                if self.version_manager:
                    self.version_manager.save_state(f"Rename instance: {old_name} -> {new_name}")

            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to rename instance: {e}")

    def add_pin(self):
        """Add a new pin to the selected object."""
        self._deactivate_mode()
        QMessageBox.information(self, "Add Pin",
                                "Click inside the visible block to add a pin (copied into its instances).")

        def handler(ev):
            pos = self.view.mapToScene(ev.position().toPoint())
            for bf in self.controller.blocks.values():
                if bf.isVisible() and bf.mapRectToScene(bf.rect()).contains(pos):
                    self._controller_add_block_pin_at_point(bf, pos)
                    self.view.viewport().removeEventFilter(filter_obj)
                    if self.version_manager:
                        self.version_manager.save_state(f"Add pin")
                    return True
            return False

        class OneShot(QObject):
            def eventFilter(self, obj, ev):
                if ev.type() == 2:
                    return handler(ev)
                return False

        filter_obj = OneShot()
        self.view.viewport().installEventFilter(filter_obj)

    def _controller_add_block_pin_at_point(self, block_frame: BlockFrame,
                                           scene_pos: QPointF):
        """Add block pin at specific point."""
        local = block_frame.mapFromScene(scene_pos)
        rect = block_frame.rect()
        lx = min(max(local.x(), 0.0), rect.width())
        ly = min(max(local.y(), 0.0), rect.height())
        left = lx
        right = rect.width() - lx
        top = ly
        bottom = rect.height() - ly
        m = min(left, right, top, bottom)
        if m == left:
            nx, ny = 0.0, ly
        elif m == right:
            nx, ny = rect.width(), ly
        elif m == top:
            nx, ny = lx, 0.0
        else:
            nx, ny = lx, rect.height()
        relx = nx / rect.width() if rect.width() else 0.0
        rely = ny / rect.height() if rect.height() else 0.0
        pm = block_frame.add_block_pin(name=None, relx=relx, rely=rely)
        
        # Add to object model
        block_name = block_frame.model.name
        if block_name in self.netlist_project.blocks:
            try:
                self.netlist_project.add_pin_to_block(block_name, pm.name)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to add pin to model: {e}")
        
        self.controller.show_only_block(self._current_block_id)

    def delete_pin(self):
        """Delete the selected pin from both models."""
        selected = list(self.scene.selectedItems())
        ports = [it for it in selected if isinstance(it, PortItem)]
        if not ports:
            QMessageBox.information(self, "Delete Pin", "Select a pin to delete.")
            return
        for p in ports:
            if p.owner_id and p.owner_id.startswith("block:"):
                block_id = p.owner_id.split(":", 1)[1]
                block_frame = self.controller.blocks.get(block_id)
                if block_frame:
                    block_name = block_frame.model.name
                    pin_name = p.model.name
                    # Remove from object model
                    if block_name in self.netlist_project.blocks:
                        try:
                            self.netlist_project.remove_pin_from_block(
                                block_name, pin_name
                            )
                            if self.version_manager:
                                self.version_manager.save_state(f"Delete pin: {p.model.name}")
                        except Exception as e:
                            QMessageBox.warning(self, "Error", f"Failed to delete pin: {e}")
                self.controller.delete_block_pin(p)
            else:
                QMessageBox.information(
                    self, "Delete Pin", "Only block-level pins can be deleted."
                )

    def rename_pin(self):
        """Rename the selected pin in both models."""
        selected = list(self.scene.selectedItems())
        ports = [it for it in selected if isinstance(it, PortItem)]
        if not ports:
            QMessageBox.information(self, "Rename Pin", "Select a pin to rename.")
            return
        pin = ports[0]
        new_name, ok = QInputDialog.getText(
            self, "Rename Pin", "New name:", text=pin.model.name
        )
        if ok and new_name:
            try:
                if pin.owner_id and pin.owner_id.startswith("block:"):
                    block_id = pin.owner_id.split(":", 1)[1]
                    block_frame = self.controller.blocks.get(block_id)
                    if block_frame:
                        block_name = block_frame.model.name
                        old_name = pin.model.name
                        # Update object model
                        if block_name in self.netlist_project.blocks:
                            self.netlist_project.rename_pin_in_block(
                                block_name, old_name, new_name
                            )
                        if self.version_manager:
                            self.version_manager.save_state(f"Rename pin: {old_name} -> {new_name}")
                # Update graphical model
                pin.model.name = new_name
                pin.label.setText(new_name)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to rename pin: {e}")

    def add_net(self):
        """Add a new net connection (wire)."""
        if self.active_mode == 'wire':
            self._deactivate_mode()
            return

        self._deactivate_mode()
        self.active_mode = 'wire'
        self.controller.set_add_wire_mode(True)

        QMessageBox.information(self, "Add Wire",
                                "Click a pin/junction to start, then click another pin/junction to complete the wire. Click 'Add Wire' again to cancel.")

        def handler(ev):
            if ev.button() != Qt.MouseButton.LeftButton:
                return False

            pos = self.view.mapToScene(ev.position().toPoint())
            items = self.scene.items(pos)

            item = None
            for it in items:
                if isinstance(it, (PortItem, JunctionItem)):
                    item = it
                    break

            if item is None:
                return False

            if self.controller.temp_wire_start is None:
                self.controller.start_wire(item)
                return True
            else:
                self.controller.finish_wire(item)
                # Add to object model if wire was created
                if self.controller.temp_wire_start and hasattr(self.controller, '_visible_block_id'):
                    try:
                        block_id = self.controller._visible_block_id
                        for bid, bf in self.controller.blocks.items():
                            if bid == block_id:
                                block_name = bf.model.name
                                if block_name in self.netlist_project.blocks:
                                    # Wire is already in the model via controller
                                    pass
                                break
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to add net to model: {e}")
                self._deactivate_mode()
                if self.version_manager:
                    self.version_manager.save_state("Add net")
                return True

        class WireModeFilter(QObject):
            def eventFilter(self, obj, ev):
                if ev.type() == 2:
                    return handler(ev)
                return False

        self.current_filter = WireModeFilter()
        self.view.viewport().installEventFilter(self.current_filter)

    def delete_net(self):
        """Delete the selected net (wire)."""
        selected = list(self.scene.selectedItems())
        wires = [it for it in selected if isinstance(it, WireItem)]
        if not wires:
            QMessageBox.information(self, "Delete Wire", "Select a wire to delete.")
            return
        for w in wires:
            self.controller.delete_wire(w)

            if self.version_manager:
                self.version_manager.save_state(f"Delete net")

    def rename_net(self):
        """Rename the selected net."""
        QMessageBox.information(
            self, "Rename Net", "Wire renaming is not yet supported."
        )

    def add_junction(self):
        """Add a new junction on an existing wire."""
        if self.active_mode == 'junction':
            self._deactivate_mode()
            return

        self._deactivate_mode()
        self.active_mode = 'junction'
        self.controller.set_add_junction_mode(True)

        QMessageBox.information(self, "Add Junction",
                                "Click on an existing wire to add a junction. Click 'Add Junction' again to cancel.")

        def handler(ev):
            if ev.button() != Qt.MouseButton.LeftButton:
                return False

            pos = self.view.mapToScene(ev.position().toPoint())
            items = self.scene.items(pos)

            for it in items:
                if isinstance(it, JunctionItem):
                    return False

            wire_item = None
            for it in items:
                if isinstance(it, WireItem):
                    wire_item = it
                    break

            if wire_item is not None:
                self.controller.create_junction_at(pos, wire_item)
                self._deactivate_mode()
                return True

            return False

        class JunctionModeFilter(QObject):
            def eventFilter(self, obj, ev):
                if ev.type() == 2:
                    result = handler(ev)
                    if result:
                        ev.accept()
                        return True
                    return False
                return False

        self.current_filter = JunctionModeFilter()
        self.view.viewport().installEventFilter(self.current_filter)

        if self.version_manager:
            self.version_manager.save_state("Add junction")

    def delete_junction(self):
        """Delete the selected junction."""
        selected = list(self.scene.selectedItems())
        junctions = [it for it in selected if isinstance(it, JunctionItem)]
        if not junctions:
            QMessageBox.information(
                self, "Delete Junction", "Select a junction to delete."
            )
            return
        for j in junctions:
            self.controller.delete_junction(j)
            if self.version_manager:
                self.version_manager.save_state(f"Delete junction")

    def undo(self):
        """Undo the last action."""
        if self.version_manager:
            if self.version_manager.undo():
                QMessageBox.information(self, "Undo", "Undo successful")
                self.refresh_objects_list()
            else:
                QMessageBox.information(self, "Undo", "No more actions to undo")
        else:
            QMessageBox.warning(self, "Undo", "Version manager not initialized")

    def redo(self):
        """Redo the last undone action."""
        if self.version_manager:
            if self.version_manager.redo():
                QMessageBox.information(self, "Redo", "Redo successful")
                self.refresh_objects_list()
            else:
                QMessageBox.information(self, "Redo", "No more actions to redo")
        else:
            QMessageBox.warning(self, "Redo", "Version manager not initialized")

    def _block_name_exists(self, name: str, exclude_id: str = None) -> bool:
        """Check if a block name already exists."""
        for block_id, block_frame in self.controller.blocks.items():
            if exclude_id and block_id == exclude_id:
                continue
            if block_frame.model.name == name:
                return True
        return False

    def _instance_name_exists_in_block(self, block_frame: BlockFrame, name: str, exclude_id: str = None) -> bool:
        """Check if an instance name already exists in a given block."""
        for inst in block_frame.model.instances:
            if exclude_id and inst.id == exclude_id:
                continue
            if inst.name == name:
                return True
        return False


def main():
    app = QApplication(sys.argv)
    editor = Editor()
    editor.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
